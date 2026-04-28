"""Product Hunt — Tier A primary for software (SW only)."""

from __future__ import annotations

from discovery.base import DiscoveryContext, DiscoveryResult, DiscoverySource


class ProductHuntDiscovery(DiscoverySource):
    """
    Free API + HTML fallback. Launch date, upvotes, tags, maker info, website.

    Best for recent software launches (last 24 months); upvotes as traction proxy.
    """

    source_name = "product_hunt"
    tier = "A"
    verticals = ["SW"]

    async def discover(self, ctx: DiscoveryContext) -> DiscoveryResult:
        raise NotImplementedError(
            "ProductHuntDiscovery.discover: call Product Hunt API or fallback HTML; "
            "return candidates with domain, name, product_hunt_launch_date, upvotes, tags."
        )
