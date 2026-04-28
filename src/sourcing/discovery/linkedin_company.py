"""LinkedIn company pages — Tier B signal + fallback (SW + HC); throttle heavily."""

from __future__ import annotations

from discovery.base import DiscoveryContext, DiscoveryResult, DiscoverySource


class LinkedInCompanyDiscovery(DiscoverySource):
    """
    Public HTML only where permitted. Industry, headcount range, founding year, description, website.

    Map: max 1 req / 10s; use mainly for validation and fallback discovery.
    """

    source_name = "linkedin_company"
    tier = "B"
    verticals = ["SW", "HC"]

    async def discover(self, ctx: DiscoveryContext) -> DiscoveryResult:
        raise NotImplementedError(
            "LinkedInCompanyDiscovery.discover: throttled public page fetch; "
            "return candidates with linkedin_url, industry, employee_count band, website."
        )
