"""Operation 2: YC directory lookup for founders + latest news.

See ``design_docs/enrichment_redesign.md`` §2.

Pipeline:
1. Slugify the company name and request ``ycombinator.com/companies/{slug}``.
2. 404 → company is not in YC's directory; drop the slice cleanly.
3. Parse the embedded ``__NEXT_DATA__`` JSON for founders + latest launch.
4. Emit one provenance entry per attribute (``founders``, ``latest_news``).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import httpx

from config import settings
from enrichment.base import EnrichmentContext, EnrichmentOperation, OperationResult
from enrichment.yc_directory_client import (
    YCDirectoryError,
    fetch_yc_company,
)
from shared.models.company import AttributeProvenance
from shared.models.enums import SourceType

logger = logging.getLogger("sourcing.enrichment.yc_directory_lookup")

DROP_MISSING_NAME = "missing_company_name"
DROP_NOT_IN_YC = "not_in_yc_directory"
DROP_FETCH_FAILED = "yc_fetch_failed"
DROP_PARSE_FAILED = "yc_parse_failed"
DROP_NO_SIGNALS = "no_yc_signals"

# YC's directory is an authoritative, structured source — confidence is high.
_YC_CONFIDENCE = 0.9


class YCDirectoryLookup(EnrichmentOperation):
    """Operation 2 — pull founders + latest news from the YC company profile."""

    operation_name = "yc_directory_lookup"

    async def run(self, ctx: EnrichmentContext) -> OperationResult:
        result = OperationResult(operation_name=self.operation_name)
        company_name = (ctx.company.name or "").strip()

        if not company_name:
            return _drop(result, DROP_MISSING_NAME)

        try:
            async with httpx.AsyncClient(
                timeout=settings.enrichment_http_timeout_s
            ) as client:
                profile = await fetch_yc_company(company_name, client=client)
        except (YCDirectoryError, httpx.HTTPError) as e:
            logger.warning(
                "yc_directory: fetch failed company=%s error=%s", company_name, e
            )
            result.errors.append(f"yc:{type(e).__name__}:{e}")
            return _drop(result, DROP_FETCH_FAILED)

        if profile is None:
            logger.info("yc_directory: not in directory company=%s", company_name)
            return _drop(result, DROP_NOT_IN_YC)

        attrs: dict[str, object] = {}
        if profile.founders:
            attrs["founders"] = [
                {"full_name": f.full_name, "title": f.title} for f in profile.founders
            ]
        if profile.latest_news is not None:
            posted = profile.latest_news.posted_at
            attrs["latest_news"] = {
                "title": profile.latest_news.title,
                "url": profile.latest_news.url,
                "posted_at": posted.isoformat() if posted else None,
                "tagline": profile.latest_news.tagline,
            }

        if not attrs:
            logger.info(
                "yc_directory: no signals on profile company=%s url=%s",
                company_name,
                profile.profile_url,
            )
            return _drop(result, DROP_NO_SIGNALS)

        now = datetime.now(timezone.utc)
        provenance: dict[str, AttributeProvenance] = {}
        for key, value in attrs.items():
            normalized = json.dumps(value, sort_keys=True, default=str)
            provenance[key] = AttributeProvenance(
                source_name=self.operation_name,
                source_type=SourceType.SCRAPE,
                observed_value=value,
                normalized_value=normalized,
                confidence=_YC_CONFIDENCE,
                evidence_urls=[profile.profile_url],
                snippet=None,
                extracted_at=now,
            )

        result.attributes = attrs
        result.provenance = provenance
        logger.info(
            "yc_directory: ok company=%s founders=%d has_news=%s url=%s",
            company_name,
            len(profile.founders),
            profile.latest_news is not None,
            profile.profile_url,
        )
        return result


def _drop(result: OperationResult, reason: str) -> OperationResult:
    result.dropped = True
    result.drop_reason = reason
    return result
