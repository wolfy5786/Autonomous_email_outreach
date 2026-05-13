"""Hacker News — Tier B signal source (SW only).

Pulls recent ``Show HN`` stories via the public Algolia HN search API. Output is a
hint feed: minimal ``(name, url, story_id, domain)`` dicts that must be cross-checked
against a Tier A directory before any enrichment runs (per data_sourcing_map.md §
"Tier B signal sources" and source_map.py CATALOG).
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from discovery.base import DiscoveryContext, DiscoveryResult, DiscoverySource
from shared.models.plan import HackerNewsFilters, HackerNewsSource

logger = logging.getLogger("sourcing.discovery.hacker_news")

ALGOLIA_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
LOOKBACK_DAYS = 90
HITS_PER_PAGE = 100
HTTP_TIMEOUT_S = 30.0

_SHOW_HN_PREFIX_RE = re.compile(r"^\s*show\s+hn\s*[:\-–—]\s*", re.IGNORECASE)
_NAME_SEPARATOR_RE = re.compile(r"\s+[\-–—]\s+")


class HackerNewsDiscovery(DiscoverySource):
    """
    Algolia HN search → ``Show HN`` candidates from the last ``LOOKBACK_DAYS`` days.

    Tier B: emits hints only (``HINT_FEED`` per source_map.py); validation must
    cross-check against Tier A directories before enrichment.
    """

    source_name = "hacker_news"
    tier = "B"
    verticals = ["SW"]

    async def discover(self, ctx: DiscoveryContext) -> DiscoveryResult:
        result = DiscoveryResult(source_name=self.source_name, tier=self.tier)

        block = _hacker_news_block_from_plan(ctx.plan)
        if block is not None and not block.enabled:
            logger.info(
                "stage=hacker_news_skipped_disabled campaign_id=%s reason=plan_enabled_false",
                ctx.campaign_id,
            )
            return result

        filters = block.filters if block is not None else HackerNewsFilters()
        params = _build_algolia_params(filters, int(time.time()))

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_S) as client:
                resp = await client.get(ALGOLIA_SEARCH_URL, params=params)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPError as e:
            result.errors.append(f"http error {type(e).__name__}: {e}")
            return result
        except ValueError as e:
            result.errors.append(f"json decode error: {e}")
            return result

        hits = payload.get("hits") if isinstance(payload, dict) else None
        if not isinstance(hits, list):
            result.errors.append("unexpected payload: missing hits[]")
            return result

        skipped_no_url = 0
        skipped_filter = 0
        for hit in hits:
            if not _passes_post_filter(hit, filters):
                skipped_filter += 1
                continue
            candidate = _to_candidate(hit)
            if candidate is None:
                skipped_no_url += 1
                continue
            result.candidates.append(candidate)

        logger.info(
            "hacker_news: hits=%s emitted=%s skipped_no_url=%s skipped_filter=%s "
            "applied_filters=%s errors=%s",
            len(hits),
            len(result.candidates),
            skipped_no_url,
            skipped_filter,
            filters.model_dump(exclude_none=True),
            len(result.errors),
        )
        return result


def _hacker_news_block_from_plan(plan: Any) -> HackerNewsSource | None:
    sources = getattr(plan, "sources", None)
    if not isinstance(sources, list):
        return None
    for block in sources:
        if isinstance(block, HackerNewsSource):
            return block
        if getattr(block, "source", None) == "hacker_news":
            return HackerNewsSource.model_validate(block)
        if isinstance(block, dict) and block.get("source") == "hacker_news":
            return HackerNewsSource.model_validate(block)
    return None


def _build_algolia_params(filters: HackerNewsFilters, now_ts: int) -> dict[str, Any]:
    """Map plan filters to Algolia HN search params, preserving today's defaults."""
    if filters.tags:
        tags_param = f"({','.join(filters.tags)})" if len(filters.tags) > 1 else filters.tags[0]
    else:
        tags_param = "show_hn"

    if filters.created_after is not None:
        d = filters.created_after
        created_after_ts = int(
            datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp()
        )
    else:
        created_after_ts = now_ts - LOOKBACK_DAYS * 86400

    numeric_clauses: list[str] = [f"created_at_i>{created_after_ts}"]
    if filters.min_points is not None:
        numeric_clauses.append(f"points>={filters.min_points}")
    if filters.min_comments is not None:
        numeric_clauses.append(f"num_comments>={filters.min_comments}")

    params: dict[str, Any] = {
        "tags": tags_param,
        "numericFilters": ",".join(numeric_clauses),
        "hitsPerPage": HITS_PER_PAGE,
        "page": 0,
    }

    if filters.query is not None:
        q = filters.query.strip()
        if q:
            params["query"] = q

    return params


def _passes_post_filter(hit: dict[str, Any], filters: HackerNewsFilters) -> bool:
    """Defensive post-fetch check for numeric thresholds (Algolia may return edge cases)."""
    if filters.min_points is not None:
        points = hit.get("points")
        if not isinstance(points, int) or points < filters.min_points:
            return False
    if filters.min_comments is not None:
        comments = hit.get("num_comments")
        if not isinstance(comments, int) or comments < filters.min_comments:
            return False
    return True


def _to_candidate(hit: dict[str, Any]) -> dict[str, Any] | None:
    url = hit.get("url")
    if not isinstance(url, str) or not url.strip():
        return None

    title = hit.get("title") or ""
    name = _parse_name_from_title(title)
    domain = _extract_domain(url)

    return {
        "name": name,
        "url": url,
        "domain": domain,
        "story_id": hit.get("objectID"),
        "raw_title": title,
        "hn_points": hit.get("points"),
        "hn_created_at": hit.get("created_at"),
        "hn_author": hit.get("author"),
    }


def _parse_name_from_title(title: str) -> str | None:
    """``Show HN: Acme – AI for X`` → ``Acme``. Fallback: trimmed body after the prefix."""
    if not isinstance(title, str):
        return None
    body = _SHOW_HN_PREFIX_RE.sub("", title).strip()
    if not body:
        return None
    parts = _NAME_SEPARATOR_RE.split(body, maxsplit=1)
    candidate = parts[0].strip()
    return candidate or None


def _extract_domain(url: str) -> str | None:
    if not isinstance(url, str):
        return None
    s = url.strip()
    if not s:
        return None
    if "://" not in s:
        s = "http://" + s
    try:
        host = urlparse(s).hostname
    except ValueError:
        return None
    if not host:
        return None
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    if "." not in host:
        return None
    return host


if __name__ == "__main__":
    import json
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    class _StubPlan:
        id = "stub-plan"
        campaign_id = "stub-campaign"
        company_signals: list[str] = []
        personalization_hooks: list[str] = []

    ctx = DiscoveryContext(
        campaign_id="smoke-test",
        plan=_StubPlan(),  # type: ignore[arg-type]
    )

    result = asyncio.run(HackerNewsDiscovery().discover(ctx))
    print(f"\nsource={result.source_name} tier={result.tier}")
    print(f"candidates={len(result.candidates)} errors={len(result.errors)}")
    for err in result.errors:
        print(f"  ERR: {err}", file=sys.stderr)
    print("\nFirst 3 candidates:")
    for c in result.candidates[:3]:
        print(json.dumps(c, indent=2))
