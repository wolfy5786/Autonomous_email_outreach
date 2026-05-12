"""Operation 3: Company website landing-page extraction.

See ``design_docs/enrichment_redesign.md`` §3.

Pipeline:
1. URL resolution. If the company record already carries ``website_url``
   (or a usable ``domain``), use it. Otherwise SERP for the company name
   and take the top non-aggregator result.
2. crawl4ai single-page fetch — no navigation, no link-following, no
   sitemap discovery. crawl4ai follows the initial redirect implicitly.
3. Login wall / paywall / age-gate → drop with ``login_required``. This
   is a hard constraint from the design doc.
4. LLM extracts company_summary, value_props, target_market, signals
   from the rendered landing page only.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from config import settings
from enrichment.base import EnrichmentContext, EnrichmentOperation, OperationResult
from enrichment.crawl import CrawlError, fetch_single_page
from enrichment.llm import (
    LLMExtractionError,
    extract_company_website_info,
)
from enrichment.serp_client import SerpAPIError, find_company_website_url
from shared.models.company import AttributeProvenance
from shared.models.enums import SourceType

logger = logging.getLogger("sourcing.enrichment.company_website")

DROP_MISSING_NAME = "missing_company_name"
DROP_SERP_NOT_CONFIGURED = "serp_not_configured"
DROP_SERP_FAILED = "serp_failed"
DROP_NO_URL_RESOLVED = "no_url_resolved"
DROP_CRAWL_FAILED = "crawl_failed"
DROP_LOGIN_REQUIRED = "login_required"
DROP_LLM_FAILED = "llm_extraction_failed"
DROP_EMPTY_EXTRACTION = "empty_extraction"

# Single-source, single-page, model-extracted — same posture as op 1.
_WEBSITE_CONFIDENCE = 0.7


class CompanyWebsiteExtraction(EnrichmentOperation):
    """Operation 3 — extract a company info slice from its landing page."""

    operation_name = "company_website"

    async def run(self, ctx: EnrichmentContext) -> OperationResult:
        result = OperationResult(operation_name=self.operation_name)
        company_name = (ctx.company.name or "").strip()

        if not company_name:
            return _drop(result, DROP_MISSING_NAME)

        seed_url = _seed_url_from_company(ctx.company)

        if seed_url is None:
            api_key = settings.serpapi_api_key
            if not api_key:
                result.errors.append("SERPAPI_API_KEY is not configured")
                return _drop(result, DROP_SERP_NOT_CONFIGURED)

            try:
                async with httpx.AsyncClient(
                    timeout=settings.enrichment_http_timeout_s
                ) as client:
                    hit = await find_company_website_url(
                        company_name, api_key=api_key, client=client
                    )
            except (SerpAPIError, httpx.HTTPError) as e:
                logger.warning(
                    "company_website: SERP failed company=%s error=%s",
                    company_name,
                    e,
                )
                result.errors.append(f"serp:{type(e).__name__}:{e}")
                return _drop(result, DROP_SERP_FAILED)

            if hit is None:
                logger.info(
                    "company_website: no URL resolved company=%s", company_name
                )
                return _drop(result, DROP_NO_URL_RESOLVED)
            seed_url = hit.url

        try:
            page = await fetch_single_page(seed_url)
        except CrawlError as e:
            logger.warning(
                "company_website: crawl failed url=%s error=%s", seed_url, e
            )
            result.errors.append(f"crawl:{e}")
            return _drop(result, DROP_CRAWL_FAILED)

        if page.login_wall:
            logger.info(
                "company_website: login wall company=%s final_url=%s",
                company_name,
                page.final_url,
            )
            return _drop(result, DROP_LOGIN_REQUIRED)

        try:
            info = await extract_company_website_info(
                company_name=company_name,
                source_url=page.final_url,
                page_markdown=page.markdown,
            )
        except LLMExtractionError as e:
            logger.warning(
                "company_website: LLM extraction failed company=%s error=%s",
                company_name,
                e,
            )
            result.errors.append(f"llm:{e}")
            return _drop(result, DROP_LLM_FAILED)

        attrs: dict[str, object] = {}
        if info.company_summary:
            attrs["company_summary"] = info.company_summary
        if info.value_props:
            attrs["value_props"] = list(info.value_props)
        if info.target_market:
            attrs["target_market"] = info.target_market
        if info.signals:
            attrs["signals"] = list(info.signals)

        if not attrs:
            logger.info(
                "company_website: no signals extracted company=%s url=%s",
                company_name,
                page.final_url,
            )
            return _drop(result, DROP_EMPTY_EXTRACTION)

        attrs["source_url"] = page.final_url

        now = datetime.now(timezone.utc)
        provenance: dict[str, AttributeProvenance] = {}
        for key, value in attrs.items():
            normalized = (
                value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str)
            )
            provenance[key] = AttributeProvenance(
                source_name=self.operation_name,
                source_type=SourceType.SCRAPE,
                observed_value=value,
                normalized_value=normalized,
                confidence=_WEBSITE_CONFIDENCE,
                evidence_urls=[page.final_url],
                snippet=None,
                extracted_at=now,
            )

        result.attributes = attrs
        result.provenance = provenance
        logger.info(
            "company_website: ok company=%s url=%s keys=%s",
            company_name,
            page.final_url,
            sorted(k for k in attrs if k != "source_url"),
        )
        return result


def _seed_url_from_company(company: object) -> str | None:
    """Pull a usable seed URL from the company record without a SERP call.

    Prefers ``website_url`` (already a full URL). Falls back to ``domain``
    promoted to ``https://`` so we don't waste a SERP query when the
    sourcing layer already has the canonical site.
    """
    website = getattr(company, "website_url", None)
    if isinstance(website, str) and website.strip():
        candidate = website.strip()
        if _looks_like_http_url(candidate):
            return candidate
        return f"https://{candidate}"
    domain = getattr(company, "domain", None)
    if isinstance(domain, str) and domain.strip():
        return f"https://{domain.strip()}"
    return None


def _looks_like_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _drop(result: OperationResult, reason: str) -> OperationResult:
    result.dropped = True
    result.drop_reason = reason
    return result
