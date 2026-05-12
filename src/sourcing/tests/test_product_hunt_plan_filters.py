"""Tests for Product Hunt plan-driven filters (``discovery.product_hunt``)."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from unittest.mock import patch

from discovery.base import DiscoveryContext
from discovery.product_hunt import (
    ProductHuntDiscovery,
    _dedupe_candidates_by_domain,
    _product_hunt_block_from_plan,
    _resolve_min_upvotes,
    _topic_slug_for_api,
    _topics_for_api_queries,
    merge_ph_time_bounds,
)
from shared.models.plan import ProductHuntFilters, ProductHuntSource


def test_merge_ph_time_bounds_plan_posted_after_stricter_than_lookback() -> None:
    now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    cutoff, posted_after_iso, posted_before = merge_ph_time_bounds(
        now_utc=now,
        lookback_days=180,
        env_posted_before_iso=None,
        plan_posted_after=date(2026, 1, 1),
        plan_posted_before=None,
    )
    assert cutoff == datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert posted_after_iso == "2026-01-01T00:00:00Z"
    assert posted_before is None


def test_merge_ph_time_bounds_posted_before_intersection() -> None:
    now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    _, _, posted_before = merge_ph_time_bounds(
        now_utc=now,
        lookback_days=30,
        env_posted_before_iso="2027-01-01T00:00:00Z",
        plan_posted_after=None,
        plan_posted_before=date(2026, 3, 1),
    )
    assert posted_before == "2026-03-01T23:59:59Z"


def test_topic_slug_for_api_normalizes_label() -> None:
    assert _topic_slug_for_api("Developer Tools") == "developer-tools"
    assert _topic_slug_for_api("  AI  ") == "ai"


def test_topics_for_api_queries_uses_plan_topics_then_env() -> None:
    f = ProductHuntFilters(topics=["SaaS", "Fin Tech"])
    assert _topics_for_api_queries(f, "ignored-env") == ["saas", "fin-tech"]
    assert _topics_for_api_queries(ProductHuntFilters(topics=[]), "my-topic") == ["my-topic"]
    assert _topics_for_api_queries(None, None) == [None]


def test_resolve_min_upvotes_env_can_only_raise_bar() -> None:
    assert _resolve_min_upvotes(5, 0) == 5
    assert _resolve_min_upvotes(5, 10) == 10
    assert _resolve_min_upvotes(None, 3) == 3


def test_dedupe_candidates_by_domain_first_wins() -> None:
    rows = [
        {"domain": "a.com", "name": "first"},
        {"domain": "a.com", "name": "second"},
        {"domain": "b.com", "name": "b"},
    ]
    out = _dedupe_candidates_by_domain(rows)
    assert len(out) == 2
    assert next(c for c in out if c["domain"] == "a.com")["name"] == "first"


def test_product_hunt_block_from_plan_returns_first_block() -> None:
    class P:
        sources = [
            ProductHuntSource(
                source="product_hunt",
                enabled=True,
                filters=ProductHuntFilters(min_votes=42),
            )
        ]

    b = _product_hunt_block_from_plan(P())
    assert b is not None
    assert b.filters.min_votes == 42


def test_discover_disabled_skips_pagination_and_token() -> None:
    class P:
        sources = [ProductHuntSource(source="product_hunt", enabled=False)]

    ctx = DiscoveryContext(campaign_id="c1", plan=P())  # type: ignore[arg-type]

    async def run() -> None:
        with (
            patch("discovery.product_hunt._resolve_bearer_token", return_value=(None, None)) as tok,
            patch("discovery.product_hunt._run_ph_pagination") as pag,
        ):
            r = await ProductHuntDiscovery().discover(ctx)
        tok.assert_not_called()
        pag.assert_not_called()
        assert r.candidates == []
        assert r.errors == []

    asyncio.run(run())


def test_discover_multi_topic_dedupes_domains() -> None:
    class P:
        sources = [
            ProductHuntSource(
                source="product_hunt",
                filters=ProductHuntFilters(topics=["One", "Two"]),
            )
        ]

    ctx = DiscoveryContext(campaign_id="c1", plan=P())  # type: ignore[arg-type]

    async def fake_pagination(*, topic_slug: str | None, **kwargs: object):
        # Same domain from two topic queries — dedupe should keep one.
        return [{"domain": "same.io", "topic": topic_slug}], []

    async def run() -> None:
        with (
            patch("discovery.product_hunt._resolve_bearer_token", return_value=("tok", "oauth")),
            patch("discovery.product_hunt._run_ph_pagination", side_effect=fake_pagination),
        ):
            r = await ProductHuntDiscovery().discover(ctx)
        assert len(r.candidates) == 1
        assert r.candidates[0]["domain"] == "same.io"

    asyncio.run(run())
