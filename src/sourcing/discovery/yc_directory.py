"""Y Combinator company directory — Tier A primary (SW + HC)."""

from __future__ import annotations

from discovery.base import DiscoveryContext, DiscoveryResult, DiscoverySource


class YCDirectoryDiscovery(DiscoverySource):
    """
    HTML scrape or CSV mirror of ycombinator.com/companies.

    Key fields: name, domain, batch, description, B2B tag. Filter by Healthcare or B2B SaaS per ICP.
    """

    source_name = "yc_directory"
    tier = "A"
    verticals = ["SW", "HC"]

    async def discover(self, ctx: DiscoveryContext) -> DiscoveryResult:
        raise NotImplementedError(
            "YCDirectoryDiscovery.discover: scrape or ingest YC directory; filter by ICP; "
            "return candidates with name, domain, yc_batch, description, is_b2b_saas."
        )
