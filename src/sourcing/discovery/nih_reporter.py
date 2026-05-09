"""NIH Reporter — Tier A primary for healthcare (HC only)."""

from __future__ import annotations

from discovery.base import DiscoveryContext, DiscoveryResult, DiscoverySource


class NIHReporterDiscovery(DiscoverySource):
    """
    Free REST API (reporter.nih.gov). PI, institution, project title, abstract, funding, keywords.

    Surfaces academic spinouts; abstracts can feed ICP relevance scoring (LLM).
    """

    source_name = "nih_reporter"
    tier = "A"
    verticals = ["HC"]

    async def discover(self, ctx: DiscoveryContext) -> DiscoveryResult:
        raise NotImplementedError(
            "NIHReporterDiscovery.discover: query NIH Reporter API; map grants to organization "
            "candidates with nih_grant_amount, nih_project_abstract, institution_name."
        )
