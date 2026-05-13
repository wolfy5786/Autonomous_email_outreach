"""Y Combinator company directory — Tier A primary (SW + HC).

Fetches YC's industry-pinned static JSON via the community ``yc-oss/api`` mirror
(refreshed daily from YC's public Algolia index). Two files cover this project's
ICP verticals: B2B (software) and Healthcare.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from discovery.base import DiscoveryContext, DiscoveryResult, DiscoverySource
from shared.models.plan import YCDirectoryFilters, YCDirectorySource

logger = logging.getLogger("sourcing.discovery.yc_directory")

YC_OSS_BASE = "https://yc-oss.github.io/api/industries"
B2B_URL = f"{YC_OSS_BASE}/b2b.json"
HEALTHCARE_URL = f"{YC_OSS_BASE}/healthcare.json"
CONSUMER_URL = f"{YC_OSS_BASE}/consumer.json"

HTTP_TIMEOUT_S = 30.0


class YCDirectoryDiscovery(DiscoverySource):
    """
    Static-JSON pull from ``yc-oss/api`` for both verticals.

    Emits one dict per active company with the keys declared for ``yc_directory`` in
    ``source_map.py`` CATALOG (``domain, name, description, yc_batch, is_b2b_saas``)
    plus baseline attributes available from the YC payload and YC-specific extras.
    """

    source_name = "yc_directory"
    tier = "A"
    verticals = ["SW", "HC"]

    async def discover(self, ctx: DiscoveryContext) -> DiscoveryResult:
        result = DiscoveryResult(source_name=self.source_name, tier=self.tier)

        block = _yc_directory_block_from_plan(ctx.plan)
        if block is not None and not block.enabled:
            logger.info(
                "stage=yc_directory_skipped_disabled campaign_id=%s reason=plan_enabled_false",
                ctx.campaign_id,
            )
            return result

        filters = block.filters if block is not None else YCDirectoryFilters()

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_S) as client:
            (b2b_rows, b2b_err), (hc_rows, hc_err), (consumer_rows, consumer_err) = await asyncio.gather(
                self._fetch(client, B2B_URL, "b2b"),
                self._fetch(client, HEALTHCARE_URL, "healthcare"),
                self._fetch(client, CONSUMER_URL, "consumer"),
            )

        if b2b_err:
            result.errors.append(b2b_err)
        if hc_err:
            result.errors.append(hc_err)
        if consumer_err:
            result.errors.append(consumer_err)

        b2b_ids = {row.get("id") for row in b2b_rows if row.get("id") is not None}

        by_id: dict[Any, dict[str, Any]] = {}
        skipped_no_domain = 0
        skipped_inactive = 0
        skipped_filter = 0
        for raw in b2b_rows + hc_rows + consumer_rows:
            yc_id = raw.get("id")
            if yc_id is None or yc_id in by_id:
                continue
            candidate, reason = self._to_candidate(raw, is_b2b=(yc_id in b2b_ids), filters=filters)
            if candidate is None:
                if reason == "inactive":
                    skipped_inactive += 1
                elif reason == "no_domain":
                    skipped_no_domain += 1
                continue
            if not _candidate_matches_filters(candidate, raw, filters):
                skipped_filter += 1
                continue
            by_id[yc_id] = candidate

        result.candidates = list(by_id.values())

        logger.info(
            "yc_directory: b2b=%s hc=%s consumer=%s emitted=%s skipped_inactive=%s skipped_no_domain=%s "
            "skipped_filter=%s applied_filters=%s errors=%s",
            len(b2b_rows),
            len(hc_rows),
            len(consumer_rows),
            len(result.candidates),
            skipped_inactive,
            skipped_no_domain,
            skipped_filter,
            filters.model_dump(exclude_none=True),
            len(result.errors),
        )
        return result

    async def _fetch(
        self,
        client: httpx.AsyncClient,
        url: str,
        label: str,
    ) -> tuple[list[dict[str, Any]], str | None]:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as e:
            return [], f"{label}: http error {type(e).__name__}: {e}"
        except ValueError as e:
            return [], f"{label}: json decode error: {e}"
        if not isinstance(data, list):
            return [], f"{label}: unexpected payload type {type(data).__name__}"
        return data, None

    def _to_candidate(
        self,
        raw: dict[str, Any],
        *,
        is_b2b: bool,
        filters: YCDirectoryFilters,
    ) -> tuple[dict[str, Any] | None, str | None]:
        if filters.status is None and (raw.get("status") or "").lower() != "active":
            return None, "inactive"

        domain = _extract_domain(raw.get("website") or "")
        if not domain:
            return None, "no_domain"

        team_size = raw.get("team_size")
        employee_count = team_size if isinstance(team_size, int) and team_size > 0 else None

        headquarters = _parse_headquarters(_first_location(raw.get("all_locations")))

        tags = list(raw.get("tags") or [])
        subindustry = raw.get("subindustry")
        if subindustry and subindustry not in tags:
            tags.append(subindustry)

        batch = raw.get("batch")

        candidate = {
            "name": raw.get("name"),
            "domain": domain,
            "website_url": raw.get("website") or None,
            "description": raw.get("long_description") or raw.get("one_liner") or None,
            "industry": raw.get("industry"),
            "employee_count": employee_count,
            "headquarters": headquarters,
            "tags": tags,
            "yc_id": raw.get("id"),
            "yc_slug": raw.get("slug"),
            "yc_batch": batch,
            "yc_batch_year": _parse_batch_year(batch),
            "yc_status": raw.get("status"),
            "is_b2b_saas": is_b2b,
        }
        return candidate, None


_YEAR_IN_BATCH_RE = re.compile(r"(20\d{2}|\d{2})")


def _yc_directory_block_from_plan(plan: Any) -> YCDirectorySource | None:
    sources = getattr(plan, "sources", None)
    if not isinstance(sources, list):
        return None
    for block in sources:
        if isinstance(block, YCDirectorySource):
            return block
        if getattr(block, "source", None) == "yc_directory":
            return YCDirectorySource.model_validate(block)
        if isinstance(block, dict) and block.get("source") == "yc_directory":
            return YCDirectorySource.model_validate(block)
    return None


def _norm(s: Any) -> str | None:
    if not isinstance(s, str):
        return None
    out = s.strip().lower()
    return out or None


def _norm_set(values: list[str] | None) -> set[str]:
    if not values:
        return set()
    out: set[str] = set()
    for v in values:
        n = _norm(v)
        if n:
            out.add(n)
    return out


def _coerce_year(v: Any) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        m = _YEAR_IN_BATCH_RE.search(v)
        if not m:
            return None
        raw = m.group(1)
        return int(raw) if len(raw) == 4 else 2000 + int(raw)
    return None


def _candidate_matches_filters(
    candidate: dict[str, Any],
    raw: dict[str, Any],
    filters: YCDirectoryFilters,
) -> bool:
    if filters.status is not None:
        cand_status = _norm(candidate.get("yc_status"))
        if cand_status != filters.status.lower():
            return False

    if filters.batch_years:
        want_years = {_coerce_year(y) for y in filters.batch_years}
        want_years.discard(None)
        if candidate.get("yc_batch_year") not in want_years:
            return False

    if filters.industries:
        want = _norm_set(filters.industries)
        cand_industry = _norm(raw.get("industry"))
        cand_sub = _norm(raw.get("subindustry"))
        cand_tags = {n for n in (_norm(t) for t in (raw.get("tags") or [])) if n}
        if not (
            (cand_industry is not None and cand_industry in want)
            or (cand_sub is not None and cand_sub in want)
            or bool(cand_tags & want)
        ):
            return False

    if filters.subindustries:
        want = _norm_set(filters.subindustries)
        # Also match right-hand portion of "X -> Y" patterns (e.g. "B2B -> AI" → "ai")
        # so that companies whose tags include "AI" are not falsely excluded.
        want_parts: set[str] = {
            w.split(" -> ", 1)[1] if " -> " in w else w for w in want
        }
        cand_industry = _norm(raw.get("industry"))
        cand_sub = _norm(raw.get("subindustry"))
        cand_tags = {n for n in (_norm(t) for t in (candidate.get("tags") or [])) if n}
        if not (
            (cand_sub is not None and cand_sub in want)
            or (cand_industry is not None and cand_industry in want)
            or bool(cand_tags & want)
            or bool(cand_tags & want_parts)
        ):
            return False

    if filters.tags:
        want = _norm_set(filters.tags)
        cand_tags = {n for n in (_norm(t) for t in (candidate.get("tags") or [])) if n}
        if not (cand_tags & want):
            return False

    # TODO(regions): not enforced yet — YC API stores "United States of America" / "USA"
    # which won't match shorthand like "US". Needs a country-code alias map before enabling.
    # if filters.regions: ...

    if filters.is_hiring is not None and "isHiring" in raw:
        # Best-effort: only enforce when the field is present on the YC payload;
        # entries missing the field are kept (treated as unknown).
        if bool(raw.get("isHiring")) != filters.is_hiring:
            return False

    return True


def _extract_domain(url: str) -> str | None:
    if not isinstance(url, str):
        return None
    s = url.strip()
    if not s:
        return None
    if "://" not in s:
        s = "http://" + s
    try:
        host = urlparse(s).hostname
    except ValueError:
        return None
    if not host:
        return None
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    if "." not in host:
        return None
    return host


def _first_location(value: Any) -> str | None:
    """``all_locations`` may be a list of strings or a single comma-joined string."""
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                return item
        return None
    if isinstance(value, str):
        return value
    return None


def _parse_headquarters(loc: str | None) -> dict[str, str] | None:
    if not isinstance(loc, str):
        return None
    parts = [p.strip() for p in loc.split(",") if p.strip()]
    if not parts:
        return None
    if len(parts) == 1:
        return {"city": parts[0], "country": ""}
    return {"city": parts[0], "country": parts[-1]}


def _parse_batch_year(batch: str | None) -> int | None:
    if not isinstance(batch, str) or not batch:
        return None
    m = _YEAR_IN_BATCH_RE.search(batch)
    if not m:
        return None
    raw = m.group(1)
    return int(raw) if len(raw) == 4 else 2000 + int(raw)


if __name__ == "__main__":
    import json
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    class _StubPlan:
        id = "stub-plan"
        campaign_id = "stub-campaign"
        company_signals: list[str] = []
        personalization_hooks: list[str] = []

    ctx = DiscoveryContext(
        campaign_id="smoke-test",
        plan=_StubPlan(),  # type: ignore[arg-type]
    )

    result = asyncio.run(YCDirectoryDiscovery().discover(ctx))
    print(f"\nsource={result.source_name} tier={result.tier}")
    print(f"candidates={len(result.candidates)} errors={len(result.errors)}")
    for err in result.errors:
        print(f"  ERR: {err}", file=sys.stderr)
    print("\nFirst 3 candidates:")
    for c in result.candidates[:3]:
        print(json.dumps(c, indent=2))
