"""GitHub Trending / orgs — Tier A fallback (SW only)."""

from __future__ import annotations

from discovery.base import DiscoveryContext, DiscoveryResult, DiscoverySource


class GitHubTrendingDiscovery(DiscoverySource):
    """
    GitHub REST API. Org name, repo description, stars/forks, language, last commit.

    Map org → domain via GitHub org profile; filter by language/topics.
    """

    source_name = "github_trending"
    tier = "A"
    verticals = ["SW"]

    async def discover(self, ctx: DiscoveryContext) -> DiscoveryResult:
        raise NotImplementedError(
            "GitHubTrendingDiscovery.discover: trending/orgs API; resolve org website/domain; "
            "return candidates with tech_stack, github_org_url, name."
        )
