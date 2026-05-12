"""Operation 3: Company website landing-page extraction.

See ``design_docs/enrichment_redesign.md`` §3. Not implemented in this session.
"""

from __future__ import annotations

from enrichment.base import EnrichmentContext, EnrichmentOperation, OperationResult


class CompanyWebsiteExtraction(EnrichmentOperation):
    operation_name = "company_website"

    async def run(self, ctx: EnrichmentContext) -> OperationResult:
        raise NotImplementedError(
            "CompanyWebsiteExtraction.run: SERP fallback to find URL → crawl4ai "
            "landing page only (no link-following) → LLM extract "
            "company_summary, value_props, signals. Drop on login wall."
        )
