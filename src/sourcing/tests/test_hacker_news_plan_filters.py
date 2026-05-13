"""Tests for Hacker News plan-driven filters (``discovery.hacker_news``)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from discovery.hacker_news import (
    LOOKBACK_DAYS,
    _build_algolia_params,
    _hacker_news_block_from_plan,
    _passes_post_filter,
)
from shared.models.plan import HackerNewsFilters, HackerNewsSource


NOW_TS = 1_800_000_000  # arbitrary fixed epoch for deterministic asserts


def test_block_from_plan_returns_first_hn_block() -> None:
    class P:
        sources = [
            HackerNewsSource(
                source="hacker_news",
                enabled=True,
                filters=HackerNewsFilters(min_points=10),
            )
        ]

    b = _hacker_news_block_from_plan(P())
    assert b is not None
    assert b.filters.min_points == 10


def test_block_from_plan_validates_dict_via_discriminator() -> None:
    class P:
        sources = [
            {"source": "hacker_news", "enabled": False, "filters": {"query": "agent"}}
        ]

    b = _hacker_news_block_from_plan(P())
    assert b is not None
    assert b.enabled is False
    assert b.filters.query == "agent"


def test_block_from_plan_none_when_missing() -> None:
    class P:
        sources: list[Any] = []

    assert _hacker_news_block_from_plan(P()) is None
    assert _hacker_news_block_from_plan(None) is None


def test_build_algolia_params_defaults_preserve_current_behavior() -> None:
    params = _build_algolia_params(HackerNewsFilters(), NOW_TS)
    expected_ts = NOW_TS - LOOKBACK_DAYS * 86400
    assert params["tags"] == "show_hn"
    assert params["numericFilters"] == f"created_at_i>{expected_ts}"
    assert params["hitsPerPage"] > 0
    assert params["page"] == 0
    assert "query" not in params


def test_build_algolia_params_tags_join() -> None:
    # Multiple tags use Algolia OR syntax (parentheses) — show_hn and launch_hn are mutually exclusive
    f = HackerNewsFilters(tags=["launch_hn", "show_hn"])
    params = _build_algolia_params(f, NOW_TS)
    assert params["tags"] == "(launch_hn,show_hn)"


def test_build_algolia_params_single_tag_no_parens() -> None:
    f = HackerNewsFilters(tags=["show_hn"])
    params = _build_algolia_params(f, NOW_TS)
    assert params["tags"] == "show_hn"


def test_build_algolia_params_created_after_overrides_lookback() -> None:
    f = HackerNewsFilters(created_after=date(2026, 1, 1))
    params = _build_algolia_params(f, NOW_TS)
    expected_ts = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
    assert params["numericFilters"] == f"created_at_i>{expected_ts}"


def test_build_algolia_params_min_points_and_comments_appended() -> None:
    f = HackerNewsFilters(min_points=50, min_comments=10)
    params = _build_algolia_params(f, NOW_TS)
    clauses = params["numericFilters"].split(",")
    assert any(c.startswith("created_at_i>") for c in clauses)
    assert "points>=50" in clauses
    assert "num_comments>=10" in clauses


def test_build_algolia_params_query_included_when_non_empty() -> None:
    assert "query" not in _build_algolia_params(HackerNewsFilters(query="   "), NOW_TS)
    p = _build_algolia_params(HackerNewsFilters(query="  ai agents  "), NOW_TS)
    assert p["query"] == "ai agents"


def test_passes_post_filter_thresholds() -> None:
    f = HackerNewsFilters(min_points=50, min_comments=10)
    assert _passes_post_filter({"points": 100, "num_comments": 20}, f) is True
    assert _passes_post_filter({"points": 10, "num_comments": 20}, f) is False
    assert _passes_post_filter({"points": 100, "num_comments": 5}, f) is False
    # Missing fields are treated as failing the threshold (defensive).
    assert _passes_post_filter({}, f) is False


def test_passes_post_filter_none_thresholds_always_pass() -> None:
    assert _passes_post_filter({}, HackerNewsFilters()) is True
    assert _passes_post_filter({"points": 0, "num_comments": 0}, HackerNewsFilters()) is True
