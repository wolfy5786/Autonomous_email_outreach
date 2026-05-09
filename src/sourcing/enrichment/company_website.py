"""Company website + blog — crawl4ai → markdown → LLM extraction."""

from __future__ import annotations

from enrichment.base import EnrichmentContext, EnrichmentResult, EnrichmentSource


class CompanyWebsiteEnrichment(EnrichmentSource):
    """
    Primary web enrichment: product description, ICP signals, pricing hints, tech, announcements.

    Cache markdown per domain (TTL ~30 days per map).
    """

    source_name = "company_website"

    async def enrich(self, ctx: EnrichmentContext) -> EnrichmentResult:
        raise NotImplementedError(
            "CompanyWebsiteEnrichment.enrich: crawl4ai fetch homepage/blog; LLM extract to schema; "
            "attach evidence_urls and AttributeProvenance per field."
        )
