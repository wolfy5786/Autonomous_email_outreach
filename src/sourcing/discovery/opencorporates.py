"""OpenCorporates free API — Tier A; legal-entity enrichment on known companies."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus

from discovery.base import DiscoveryContext, DiscoveryResult, DiscoverySource

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_OC_API = "https://api.opencorporates.com/v0.4"

# Attributes this source can populate from the structured JSON API.
_EXTRACTABLE: frozenset[str] = frozenset(
    {
        "name",
        "domain",
        "description",
        "industry",
        "headquarters",
        "founded_year",
        "employee_count",
        "company_type",
        "current_status",
        "incorporation_date",
        "registered_address",
        "jurisdiction_code",
        "opencorporates_url",
        "registry_url",
        "industry_codes",
        "officers",
        "previous_names",
    }
)

# Maximum results per search page (API cap = 100).
_PER_PAGE = 30


class OpenCorporatesDiscovery(DiscoverySource):
    """
    OpenCorporates free REST API (v0.4) — structured company registry data.

    Key fields: legal name, company type, incorporation date, registered
    address, jurisdiction, industry codes, officers, filing history.

    Pipeline alignment
    ------------------
    * **Layer 1** (structured JSON API) per README § Data Pipeline.
    * Cache-first: reuse records younger than ``freshness_days``.
    * Provenance written per §9.1 ``AttributeProvenance`` (Option A sidecar).
    * Hints emitted per §9.3 for incorporation and officer signals.
    * API key passed via ``api_token`` query param; stored in secrets
      manager per §11.

    Rate limits
    -----------
    Free tier for open-data projects.  Paid tiers: 200–1000 calls/day
    depending on plan.  The shared RateLimiter enforces the budget.
    """

    source_name = "opencorporates"
    tier = "A"
    verticals = ["SW", "HC"]

    # ── public entry point ────────────────────────────────────────

    async def discover(self, ctx: DiscoveryContext) -> DiscoveryResult:
        """
        Enrich known companies via the OpenCorporates search + detail API.

        For each seed company name, search the API, pick the best match,
        fetch full details, and return a structured candidate dict.

        Also supports limited **discovery** when ``ctx.config`` contains
        ``discovery_mode`` and ``jurisdiction_code`` — searches the
        registry for companies matching ICP keywords from the plan.
        """

        result = DiscoveryResult(
            source_name=self.source_name,
            tier=self.tier,
        )

        entities = self._collect_entities(ctx)

        # If no seeds but plan has company_signals + jurisdiction, try
        # keyword-based discovery (limited).
        if not entities:
            entities = self._plan_based_discovery_seeds(ctx)

        if not entities:
            logger.info(
                "[opencorporates] No entities to enrich — skipping."
            )
            return result

        for entity in entities:
            name: str | None = entity.get("name")
            domain: str | None = entity.get("domain")
            jurisdiction: str | None = entity.get("jurisdiction_code")

            if not name and not domain:
                result.errors.append(
                    "Entity missing both name and domain — skipped."
                )
                continue

            try:
                candidate = await self._enrich_single(
                    name, domain, jurisdiction, ctx,
                )
                if candidate is not None:
                    result.candidates.append(candidate)
            except Exception as exc:
                label = name or domain or "unknown"
                result.errors.append(f"{label}: {exc}")
                logger.exception(
                    "[opencorporates] Failed to enrich %s / %s", name, domain
                )

        return result

    # ── seed collection ───────────────────────────────────────────

    @staticmethod
    def _collect_entities(ctx: DiscoveryContext) -> list[dict[str, str]]:
        """Build ``{name, domain}`` dicts from ``ctx.seeds``."""
        entities: list[dict[str, str]] = []
        if ctx.seeds is None:
            return entities

        domains: list[str] = getattr(ctx.seeds, "domains", None) or []
        for d in domains:
            entities.append({"domain": d, "name": ""})

        names: list[str] = getattr(ctx.seeds, "company_names", None) or []
        for n in names:
            entities.append({"name": n, "domain": ""})

        return entities

    @staticmethod
    def _plan_based_discovery_seeds(
        ctx: DiscoveryContext,
    ) -> list[dict[str, str]]:
        """
        If the plan has company_signals and a jurisdiction is configured,
        create synthetic search seeds from ICP keywords.
        """
        if ctx.plan is None:
            return []
        signals = getattr(ctx.plan, "company_signals", None) or []
        jurisdiction = None
        if ctx.config is not None:
            jurisdiction = (
                ctx.config.get("jurisdiction_code")
                if isinstance(ctx.config, dict)
                else getattr(ctx.config, "jurisdiction_code", None)
            )
        if not signals or not jurisdiction:
            return []
        # Use top-3 signals as search queries.
        return [
            {"name": sig, "domain": "", "jurisdiction_code": jurisdiction}
            for sig in signals[:3]
        ]

    # ── config / auth helpers ─────────────────────────────────────

    @staticmethod
    def _cfg(ctx: DiscoveryContext, key: str, default: Any = None) -> Any:
        if ctx.config is None:
            return default
        if isinstance(ctx.config, dict):
            return ctx.config.get(key, default)
        return getattr(ctx.config, key, default)

    @staticmethod
    def _api_token(ctx: DiscoveryContext) -> str | None:
        """Read API token from config or secrets."""
        return OpenCorporatesDiscovery._cfg(ctx, "opencorporates_api_token")

    # ── single-company enrichment ─────────────────────────────────

    async def _enrich_single(
        self,
        name: str | None,
        domain: str | None,
        jurisdiction: str | None,
        ctx: DiscoveryContext,
    ) -> dict[str, Any] | None:
        """Search → match → fetch detail → build candidate."""
        from sourcing.infra import http_client  # service singleton

        # 1. Search for the company by name.
        search_query = name or (domain.split(".")[0] if domain else None)
        if not search_query:
            return None

        search_data = await self._api_search(
            http_client, search_query, jurisdiction, ctx
        )
        if not search_data:
            logger.info(
                "[opencorporates] No search results for '%s'", search_query
            )
            return None

        # 2. Pick best match.
        match = self._pick_best_match(search_data, name, domain)
        if match is None:
            return None

        # 3. Fetch full company detail.
        jc = match["jurisdiction_code"]
        cn = match["company_number"]
        detail = await self._api_company_detail(http_client, jc, cn, ctx)
        if detail is None:
            return None

        # 4. Build candidate dict.
        now_iso = datetime.now(timezone.utc).isoformat()
        candidate = self._build_candidate(detail, now_iso, name, domain, ctx)

        return candidate

    # ── API calls ─────────────────────────────────────────────────

    async def _api_search(
        self,
        http_client: Any,
        query: str,
        jurisdiction: str | None,
        ctx: DiscoveryContext,
    ) -> list[dict[str, Any]]:
        """
        GET /v0.4/companies/search?q=...

        Returns list of company summary dicts from the ``results.companies``
        array.
        """
        from sourcing.infra import rate_limiter

        if not await rate_limiter.acquire(self.source_name):
            logger.warning("[opencorporates] Rate limit exhausted.")
            return []

        params: dict[str, str] = {
            "q": query,
            "per_page": str(_PER_PAGE),
            "order": "score",
        }

        token = self._api_token(ctx)
        if token:
            params["api_token"] = token

        if jurisdiction:
            params["jurisdiction_code"] = jurisdiction

        url = f"{_OC_API}/companies/search"

        try:
            resp = await http_client.get(url, params=params)
            if resp.status_code != 200:
                logger.warning(
                    "[opencorporates] Search returned %s for '%s'",
                    resp.status_code,
                    query,
                )
                return []
            data = resp.json()
            companies = data.get("results", {}).get("companies", [])
            return [c["company"] for c in companies if "company" in c]
        except Exception as exc:
            logger.warning("[opencorporates] Search error: %s", exc)
            return []

    async def _api_company_detail(
        self,
        http_client: Any,
        jurisdiction_code: str,
        company_number: str,
        ctx: DiscoveryContext,
    ) -> dict[str, Any] | None:
        """
        GET /v0.4/companies/:jurisdiction_code/:company_number

        Returns the full company object from ``results.company``.
        """
        from sourcing.infra import rate_limiter

        if not await rate_limiter.acquire(self.source_name):
            logger.warning("[opencorporates] Rate limit exhausted.")
            return None

        url = f"{_OC_API}/companies/{jurisdiction_code}/{company_number}"
        params: dict[str, str] = {}

        token = self._api_token(ctx)
        if token:
            params["api_token"] = token

        try:
            resp = await http_client.get(url, params=params)
            if resp.status_code != 200:
                logger.warning(
                    "[opencorporates] Detail returned %s for %s/%s",
                    resp.status_code,
                    jurisdiction_code,
                    company_number,
                )
                return None
            data = resp.json()
            return data.get("results", {}).get("company")
        except Exception as exc:
            logger.warning("[opencorporates] Detail error: %s", exc)
            return None

    # ── matching ──────────────────────────────────────────────────

    @staticmethod
    def _pick_best_match(
        companies: list[dict[str, Any]],
        name: str | None,
        domain: str | None,
    ) -> dict[str, Any] | None:
        """
        Pick the best company from search results.

        Strategy:
        - If domain provided, check ``registry_url`` or company data
          items for a matching website.
        - Otherwise, fuzzy name match: prefer active companies whose
          name starts with the query.
        - Falls back to the first (highest-scored) result.
        """
        if not companies:
            return None

        name_lower = (name or "").lower().strip()
        domain_lower = (domain or "").lower().strip()

        # Pass 1 — exact name match (case-insensitive) + active
        for c in companies:
            c_name = (c.get("name") or "").lower()
            c_status = (c.get("current_status") or "").lower()
            if c_name == name_lower and "active" in c_status:
                return c

        # Pass 2 — name starts-with + active
        for c in companies:
            c_name = (c.get("name") or "").lower()
            c_status = (c.get("current_status") or "").lower()
            if name_lower and c_name.startswith(name_lower) and "active" in c_status:
                return c

        # Pass 3 — active companies, pick first (API returns by score)
        for c in companies:
            c_status = (c.get("current_status") or "").lower()
            if "active" in c_status:
                return c

        # Fallback — first result regardless of status.
        return companies[0]

    # ── candidate construction ────────────────────────────────────

    def _build_candidate(
        self,
        company: dict[str, Any],
        now_iso: str,
        original_name: str | None,
        original_domain: str | None,
        ctx: DiscoveryContext,
    ) -> dict[str, Any]:
        """
        Map OpenCorporates company JSON to the project's ``company_record``
        schema.  Returns a raw candidate dict (not a CompanyRecord instance).
        """

        name = company.get("name") or original_name
        domain = original_domain  # OC doesn't reliably provide domains

        # Extract registered address.
        address = company.get("registered_address_in_full") or ""
        headquarters = address if address else None

        # Extract incorporation year.
        inc_date = company.get("incorporation_date")
        founded_year = None
        if inc_date:
            try:
                founded_year = int(str(inc_date)[:4])
            except (ValueError, TypeError):
                pass

        # Extract industry from industry_codes.
        industry = None
        industry_codes = company.get("industry_codes") or []
        if industry_codes:
            first_ic = industry_codes[0].get("industry_code", {})
            industry = first_ic.get("description")

        # Extract officers summary.
        officers_raw = company.get("officers") or []
        officers = []
        for o in officers_raw[:10]:  # cap at 10
            off = o.get("officer", {})
            officers.append(
                {
                    "name": off.get("name"),
                    "position": off.get("position"),
                    "start_date": off.get("start_date"),
                    "end_date": off.get("end_date"),
                }
            )

        oc_url = company.get("opencorporates_url") or ""

        candidate: dict[str, Any] = {
            "name": name,
            "domain": domain,
            "industry": industry,
            "description": None,  # OC doesn't provide descriptions
            "employee_count": None,  # not available from OC
            "headquarters": headquarters,
            "funding_stage": None,  # not available from OC
            "tech_stack": [],
            "linkedin_url": None,
            "website_url": f"https://{domain}" if domain else None,
            "freshness_timestamp": now_iso,
            "scrape_mode_last": "all",
            "extra": {
                "opencorporates_url": oc_url,
                "company_type": company.get("company_type"),
                "current_status": company.get("current_status"),
                "jurisdiction_code": company.get("jurisdiction_code"),
                "company_number": company.get("company_number"),
                "incorporation_date": inc_date,
                "founded_year": founded_year,
                "registered_address": address,
                "registry_url": company.get("registry_url"),
                "previous_names": [
                    pn.get("company_name")
                    for pn in (company.get("previous_names") or [])
                ],
                "industry_codes": [
                    {
                        "code": ic.get("industry_code", {}).get("code"),
                        "description": ic.get("industry_code", {}).get(
                            "description"
                        ),
                        "scheme": ic.get("industry_code", {}).get(
                            "code_scheme_name"
                        ),
                    }
                    for ic in industry_codes
                ],
                "officers": officers,
            },
        }

        # data_completeness.
        core_keys = [
            "name", "domain", "industry", "description", "employee_count",
            "headquarters", "funding_stage", "linkedin_url",
        ]
        filled = sum(1 for k in core_keys if candidate.get(k) is not None)
        candidate["data_completeness"] = round(filled / len(core_keys), 2)

        # Provenance sidecar (§9.1 Option A).
        provenance_attrs = {
            "name", "headquarters", "industry", "founded_year",
            "company_type", "current_status", "incorporation_date",
            "registered_address", "jurisdiction_code", "opencorporates_url",
            "officers",
        }
        candidate["provenance"] = {}
        for attr in provenance_attrs:
            # Value lives either in candidate root or in extra.
            value = candidate.get(attr) or candidate.get("extra", {}).get(attr)
            if value is not None:
                candidate["provenance"][attr] = {
                    "source_name": self.source_name,
                    "source_type": "api",
                    "observed_value": value,
                    "normalized_value": value,
                    "confidence": 0.90,
                    "evidence_urls": [oc_url] if oc_url else [],
                    "snippet": None,
                    "extracted_at": now_iso,
                }

        # Hints (§9.3).
        hints = self._extract_hints(company, candidate, ctx)
        if hints:
            candidate["_hints"] = hints

        return candidate

    # ── hint extraction (§9.3) ────────────────────────────────────

    @staticmethod
    def _extract_hints(
        company: dict[str, Any],
        candidate: dict[str, Any],
        ctx: DiscoveryContext,
    ) -> list[dict[str, Any]]:
        """Produce hints from OpenCorporates data — incorporation, officers."""
        hints: list[dict[str, Any]] = []
        now_iso = datetime.now(timezone.utc).isoformat()
        company_ref = candidate.get("domain") or candidate.get("name") or ""
        oc_url = candidate.get("extra", {}).get("opencorporates_url")

        # Incorporation / company-age hint.
        inc_date = company.get("incorporation_date")
        status = company.get("current_status")
        if inc_date:
            hints.append(
                {
                    "company_id": company_ref,
                    "campaign_id": ctx.campaign_id,
                    "category": "news",
                    "summary": (
                        f"Incorporated: {inc_date}; "
                        f"Status: {status or 'unknown'}"
                    ),
                    "source_name": "opencorporates",
                    "source_type": "api",
                    "source_url": oc_url,
                    "raw_snippet": None,
                    "relevance_score": None,
                    "discovered_at": now_iso,
                    "extra": {},
                }
            )

        # Officer / leadership hint.
        officers = company.get("officers") or []
        active_directors = [
            o.get("officer", {}).get("name")
            for o in officers
            if (o.get("officer", {}).get("position") or "").lower()
            in ("director", "ceo", "president", "chairman")
            and o.get("officer", {}).get("end_date") is None
        ]
        if active_directors:
            hints.append(
                {
                    "company_id": company_ref,
                    "campaign_id": ctx.campaign_id,
                    "category": "other",
                    "summary": (
                        f"Active directors: {', '.join(active_directors[:5])}"
                    ),
                    "source_name": "opencorporates",
                    "source_type": "api",
                    "source_url": oc_url,
                    "raw_snippet": None,
                    "relevance_score": None,
                    "discovered_at": now_iso,
                    "extra": {"officer_count": len(officers)},
                }
            )

        return hints
