"""Tests for YC Directory plan-driven filters (``discovery.yc_directory``)."""

from __future__ import annotations

from typing import Any

from discovery.yc_directory import (
    _candidate_matches_filters,
    _yc_directory_block_from_plan,
)
from shared.models.plan import YCDirectoryFilters, YCDirectorySource


def _cand(**over: Any) -> dict[str, Any]:
    base = {
        "name": "Acme",
        "domain": "acme.com",
        "yc_status": "Active",
        "yc_batch": "W24",
        "yc_batch_year": 2024,
        "tags": ["SaaS", "Developer Tools"],
        "headquarters": {"city": "San Francisco", "country": "United States"},
    }
    base.update(over)
    return base


def _raw(**over: Any) -> dict[str, Any]:
    base = {
        "industry": "B2B",
        "subindustry": "Engineering",
        "regions": ["United States"],
    }
    base.update(over)
    return base


def test_block_from_plan_returns_first_yc_directory_block() -> None:
    class P:
        sources = [
            YCDirectorySource(
                source="yc_directory",
                enabled=True,
                filters=YCDirectoryFilters(industries=["B2B"]),
            )
        ]

    b = _yc_directory_block_from_plan(P())
    assert b is not None
    assert b.filters.industries == ["B2B"]


def test_block_from_plan_validates_dict_via_discriminator() -> None:
    class P:
        sources = [{"source": "yc_directory", "enabled": False, "filters": {"status": "Inactive"}}]

    b = _yc_directory_block_from_plan(P())
    assert b is not None
    assert b.enabled is False
    assert b.filters.status == "Inactive"


def test_block_from_plan_none_when_missing() -> None:
    class P:
        sources: list[Any] = []

    class Q:
        pass

    assert _yc_directory_block_from_plan(P()) is None
    assert _yc_directory_block_from_plan(Q()) is None
    assert _yc_directory_block_from_plan(None) is None


def test_empty_filters_match_everything() -> None:
    assert _candidate_matches_filters(_cand(), _raw(), YCDirectoryFilters()) is True


def test_status_case_insensitive() -> None:
    f = YCDirectoryFilters(status="Active")
    assert _candidate_matches_filters(_cand(yc_status="active"), _raw(), f) is True
    assert _candidate_matches_filters(_cand(yc_status="Inactive"), _raw(), f) is False


def test_batch_years_int_match_and_string_normalization() -> None:
    f_int = YCDirectoryFilters(batch_years=["2024"])
    assert _candidate_matches_filters(_cand(yc_batch_year=2024), _raw(), f_int) is True
    assert _candidate_matches_filters(_cand(yc_batch_year=2023), _raw(), f_int) is False

    # YC-style batch token "W24" → 2024
    f_token = YCDirectoryFilters(batch_years=["W24"])
    assert _candidate_matches_filters(_cand(yc_batch_year=2024), _raw(), f_token) is True


def test_industries_case_insensitive() -> None:
    f = YCDirectoryFilters(industries=["b2b"])
    assert _candidate_matches_filters(_cand(), _raw(industry="B2B"), f) is True
    assert _candidate_matches_filters(_cand(), _raw(industry="Healthcare"), f) is False


def test_industries_falls_back_to_subindustry_and_tags() -> None:
    # "Gaming" isn't a top-level YC industry — it appears as a tag or subindustry.
    f = YCDirectoryFilters(industries=["Gaming"])
    # Match via raw["tags"]
    assert _candidate_matches_filters(_cand(), _raw(industry="B2B", tags=["Gaming", "B2B"]), f) is True
    # Match via raw["subindustry"]
    assert _candidate_matches_filters(_cand(), _raw(industry="B2B", subindustry="Gaming"), f) is True
    # No match
    assert _candidate_matches_filters(_cand(), _raw(industry="B2B", tags=["FinTech"]), f) is False


def test_subindustries_case_insensitive() -> None:
    f = YCDirectoryFilters(subindustries=["engineering"])
    assert _candidate_matches_filters(_cand(), _raw(subindustry="Engineering"), f) is True
    assert _candidate_matches_filters(_cand(), _raw(subindustry="Sales"), f) is False


def test_subindustries_falls_back_to_industry_and_tags() -> None:
    # YC raw.subindustry is null/absent for most companies — the subindustries
    # filter should still match via industry or tags so planner outputs like
    # subindustries=["SaaS"] don't drop everything.
    f = YCDirectoryFilters(subindustries=["SaaS"])
    # Match via candidate tags
    assert (
        _candidate_matches_filters(_cand(tags=["SaaS", "Other"]), _raw(subindustry=None), f)
        is True
    )
    # Match via raw["industry"]
    assert (
        _candidate_matches_filters(_cand(tags=[]), _raw(industry="SaaS", subindustry=None), f)
        is True
    )
    # No match — neither subindustry, industry, nor tags overlap
    assert (
        _candidate_matches_filters(
            _cand(tags=["Other"]), _raw(industry="B2B", subindustry=None), f
        )
        is False
    )


def test_tags_intersection_case_insensitive() -> None:
    f = YCDirectoryFilters(tags=["SaaS"])
    assert _candidate_matches_filters(_cand(tags=["saas", "Other"]), _raw(), f) is True
    assert _candidate_matches_filters(_cand(tags=["Other"]), _raw(), f) is False


def test_regions_match_country_or_raw_regions() -> None:
    f = YCDirectoryFilters(regions=["United States"])
    assert _candidate_matches_filters(_cand(), _raw(), f) is True

    # Match via raw["regions"] when headquarters country doesn't match
    assert _candidate_matches_filters(
        _cand(headquarters={"city": "London", "country": "United Kingdom"}),
        _raw(regions=["United States"]),
        f,
    ) is True

    # No overlap
    assert _candidate_matches_filters(
        _cand(headquarters={"city": "London", "country": "United Kingdom"}),
        _raw(regions=["Europe"]),
        f,
    ) is False


def test_is_hiring_best_effort_keeps_unknown() -> None:
    f = YCDirectoryFilters(is_hiring=True)
    # Field missing → keep
    assert _candidate_matches_filters(_cand(), _raw(), f) is True
    # Field present and matches → keep
    assert _candidate_matches_filters(_cand(), _raw(isHiring=True), f) is True
    # Field present and mismatches → drop
    assert _candidate_matches_filters(_cand(), _raw(isHiring=False), f) is False
