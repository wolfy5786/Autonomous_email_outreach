"""OpenCorporates — validation / fallback enrichment."""

from __future__ import annotations

from enrichment.base import EnrichmentContext, EnrichmentResult, EnrichmentSource


class OpenCorporatesEnrichment(EnrichmentSource):
    """
    Incorporation date, officers, registered address, active status (500 req/day free tier).

    Use to confirm company is active/real; officers may seed future contact discovery (out of scope).
    """

    source_name = "opencorporates"

    async def enrich(self, ctx: EnrichmentContext) -> EnrichmentResult:
        raise NotImplementedError(
            "OpenCorporatesEnrichment.enrich: API lookup by company name/jurisdiction; "
            "return company_active_status, incorporation_date."
        )
