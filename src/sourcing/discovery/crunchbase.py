"""Crunchbase free tier — Tier A primary; prefer enrichment on known companies."""

from __future__ import annotations

from discovery.base import DiscoveryContext, DiscoveryResult, DiscoverySource


class CrunchbaseDiscovery(DiscoverySource):
    """
    HTML scrape + free CSV exports. Rate-limited (~100 queries/day).

    Key fields: funding round, round type, HQ, employee range. Map specifies use as enrichment
    on known companies, not primary list source.
    """

    source_name = "crunchbase"
    tier = "A"
    verticals = ["SW", "HC"]

    async def discover(self, ctx: DiscoveryContext) -> DiscoveryResult:
        raise NotImplementedError(
            "CrunchbaseDiscovery.discover: bounded HTML/CSV fetch; return candidates with "
            "domain, name, funding_stage, headquarters, employee_count hints."
        )
