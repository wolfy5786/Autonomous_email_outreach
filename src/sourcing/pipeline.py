"""Sourcing pipeline — orchestrates discovery → enrichment → validation."""
import asyncio
from typing import Any
from .config import config
from .cache_check import SourceCache
from .validation import deduplicate_contacts, filter_by_icp_score


class SourcingPipeline:
    """Run the full sourcing pipeline for a campaign."""

    def __init__(self) -> None:
        self._cache = SourceCache(ttl_seconds=config.cache_ttl_seconds)

    async def run(
        self,
        campaign_id: str,
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute discovery → dedup → ICP filter → publish results."""
        sources = plan.get("sources", [])
        min_score = plan.get("min_icp_score", 0.5)

        # Phase 1: Discover companies from all sources
        raw_companies: list[dict[str, Any]] = []
        for source in sources:
            companies = await self._discover(source, plan)
            raw_companies.extend(companies)

        # Phase 2: Deduplicate
        unique = deduplicate_contacts(raw_companies, key_field="domain")

        # Phase 3: Filter by cache (skip recently sourced)
        fresh = [
            c for c in unique
            if not self._cache.is_cached(c.get("name", ""), c.get("domain", ""))
        ]

        # Phase 4: ICP score filter
        qualified = filter_by_icp_score(fresh, min_score=min_score)

        # Mark all as cached
        for c in qualified:
            self._cache.mark_sourced(c.get("name", ""), c.get("domain", ""))

        return {
            "campaign_id": campaign_id,
            "total_discovered": len(raw_companies),
            "after_dedup": len(unique),
            "after_cache": len(fresh),
            "qualified": len(qualified),
            "companies": qualified,
        }

    async def _discover(self, source: str, plan: dict) -> list[dict]:
        """Dispatch to the right discovery module."""
        # Import dynamically to avoid circular deps
        if source == "yc_directory":
            from .discovery.yc_directory import discover
        elif source == "hacker_news":
            from .discovery.hacker_news import discover
        elif source == "product_hunt":
            from .discovery.product_hunt import discover
        elif source == "opencorporates":
            from .discovery.opencorporates import discover
        else:
            return []

        return await discover(plan)
