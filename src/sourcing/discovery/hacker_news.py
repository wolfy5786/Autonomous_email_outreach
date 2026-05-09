"""Hacker News — Tier B signal source (SW only); not a clean list."""

from __future__ import annotations

from discovery.base import DiscoveryContext, DiscoveryResult, DiscoverySource


class HackerNewsDiscovery(DiscoverySource):
    """
    Algolia HN API. Show HN posts, job threads, product announcements.

    Extract URL + company name only; candidates must pass Tier A validation before enrichment.
    """

    source_name = "hacker_news"
    tier = "B"
    verticals = ["SW"]

    async def discover(self, ctx: DiscoveryContext) -> DiscoveryResult:
        raise NotImplementedError(
            "HackerNewsDiscovery.discover: Algolia search for 'Show HN' / hiring threads; "
            "return minimal candidate_hint dicts (name, url, story_id) — hint_feed only."
        )
