"""Careers / jobs — Greenhouse, Lever, Ashby, /careers crawl4ai + LLM."""

from __future__ import annotations

from enrichment.base import EnrichmentContext, EnrichmentResult, EnrichmentSource


class CareersPageEnrichment(EnrichmentSource):
    """
    Hiring velocity, role types, tech stack in JDs, seniority distribution.

    Check ATS embeds separately from generic /careers HTML.
    """

    source_name = "careers_page"

    async def enrich(self, ctx: EnrichmentContext) -> EnrichmentResult:
        raise NotImplementedError(
            "CareersPageEnrichment.enrich: resolve ATS URLs; crawl4ai + LLM; populate "
            "hiring_signals, open_roles_count, tech_stack hints."
        )
