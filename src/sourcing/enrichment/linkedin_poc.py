"""Operation 1: LinkedIn POC lookup.

See ``design_docs/enrichment_redesign.md`` §1.

Pipeline:
1. SERP: ``"{company_name}" LinkedIn`` via SerpAPI.
2. Pick first organic result whose host is on linkedin.com.
3. crawl4ai single-page fetch — no navigation, no tabs, no link-following.
4. If the page resolves into a LinkedIn auth path, drop the slice.
5. LLM picks a single POC (name, title, profile URL if visible).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from config import settings
from enrichment.base import EnrichmentContext, EnrichmentOperation, OperationResult
from enrichment.crawl import CrawlError, fetch_single_page
from enrichment.llm import LLMExtractionError, extract_linkedin_poc
from enrichment.serp_client import SerpAPIError, find_company_linkedin_url
from shared.models.company import AttributeProvenance
from shared.models.enums import SourceType

logger = logging.getLogger("sourcing.enrichment.linkedin_poc")

# Drop reasons (emitted in OperationResult.drop_reason; see design doc for
# expected handling of "login_required" specifically).
DROP_MISSING_NAME = "missing_company_name"
DROP_SERP_NOT_CONFIGURED = "serp_not_configured"
DROP_SERP_FAILED = "serp_failed"
DROP_NO_LINKEDIN_URL = "no_linkedin_url"
DROP_CRAWL_FAILED = "crawl_failed"
DROP_LOGIN_REQUIRED = "login_required"
DROP_LLM_FAILED = "llm_extraction_failed"
DROP_NO_POC_VISIBLE = "no_poc_visible"

# Hand-tuned confidence: single-source, single-page, model-extracted.
_POC_CONFIDENCE = 0.7


class LinkedInPocLookup(EnrichmentOperation):
    """Operation 1 — derive a single POC for a company via its LinkedIn page."""

    operation_name = "linkedin_poc"

    async def run(self, ctx: EnrichmentContext) -> OperationResult:
        result = OperationResult(operation_name=self.operation_name)
        company_name = (ctx.company.name or "").strip()

        if not company_name:
            return _drop(result, DROP_MISSING_NAME)

        api_key = settings.serpapi_api_key
        if not api_key:
            result.errors.append("SERPAPI_API_KEY is not configured")
            return _drop(result, DROP_SERP_NOT_CONFIGURED)

        try:
            async with httpx.AsyncClient(timeout=settings.enrichment_http_timeout_s) as client:
                hit = await find_company_linkedin_url(
                    company_name, api_key=api_key, client=client
                )
        except (SerpAPIError, httpx.HTTPError) as e:
            logger.warning(
                "linkedin_poc: SERP failed company=%s error=%s", company_name, e
            )
            result.errors.append(f"serp:{type(e).__name__}:{e}")
            return _drop(result, DROP_SERP_FAILED)

        if hit is None:
            logger.info(
                "linkedin_poc: no LinkedIn URL in SERP company=%s", company_name
            )
            return _drop(result, DROP_NO_LINKEDIN_URL)

        try:
            page = await fetch_single_page(hit.url)
        except CrawlError as e:
            logger.warning(
                "linkedin_poc: crawl failed url=%s error=%s", hit.url, e
            )
            result.errors.append(f"crawl:{e}")
            return _drop(result, DROP_CRAWL_FAILED)

        if page.login_wall:
            logger.info(
                "linkedin_poc: login wall company=%s final_url=%s",
                company_name,
                page.final_url,
            )
            return _drop(result, DROP_LOGIN_REQUIRED)

        try:
            poc = await extract_linkedin_poc(
                company_name=company_name,
                source_url=page.final_url,
                page_markdown=page.markdown,
            )
        except LLMExtractionError as e:
            logger.warning(
                "linkedin_poc: LLM extraction failed company=%s error=%s",
                company_name,
                e,
            )
            result.errors.append(f"llm:{e}")
            return _drop(result, DROP_LLM_FAILED)

        if not poc.poc_name:
            logger.info(
                "linkedin_poc: no POC visible company=%s url=%s",
                company_name,
                page.final_url,
            )
            return _drop(result, DROP_NO_POC_VISIBLE)

        now = datetime.now(timezone.utc)
        attrs: dict[str, str] = {
            "poc_name": poc.poc_name,
            "evidence_url": page.final_url,
        }
        if poc.poc_title:
            attrs["poc_title"] = poc.poc_title
        if poc.poc_profile_url:
            attrs["poc_profile_url"] = poc.poc_profile_url

        provenance: dict[str, AttributeProvenance] = {
            key: AttributeProvenance(
                source_name=self.operation_name,
                source_type=SourceType.SCRAPE,
                observed_value=value,
                normalized_value=value,
                confidence=_POC_CONFIDENCE,
                evidence_urls=[page.final_url],
                snippet=poc.rationale,
                extracted_at=now,
            )
            for key, value in attrs.items()
        }

        result.attributes = dict(attrs)
        result.provenance = provenance
        logger.info(
            "linkedin_poc: ok company=%s poc_name=%s url=%s",
            company_name,
            poc.poc_name,
            page.final_url,
        )
        return result


def _drop(result: OperationResult, reason: str) -> OperationResult:
    result.dropped = True
    result.drop_reason = reason
    return result
