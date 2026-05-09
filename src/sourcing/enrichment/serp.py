"""SERP — enrichment only; anchored queries per company (name + domain)."""

from __future__ import annotations

from enrichment.base import EnrichmentContext, EnrichmentResult, EnrichmentSource


class SerpEnrichment(EnrichmentSource):
    """
    SerpAPI or equivalent. Recent news, press, funding, launches.

    Never use for bulk list harvesting; query templates from attribute map.
    """

    source_name = "serp"

    async def enrich(self, ctx: EnrichmentContext) -> EnrichmentResult:
        raise NotImplementedError(
            "SerpEnrichment.enrich: run anchored queries from rule query_template; "
            "return recent_news_summary / funding snippets with evidence URLs."
        )
