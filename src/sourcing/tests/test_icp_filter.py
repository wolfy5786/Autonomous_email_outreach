"""Unit tests for ICP score filtering."""
from src.sourcing.validation.icp_filter import filter_by_icp_score


def test_filter_above_threshold():
    prospects = [
        {"name": "A", "icp_score": 0.9},
        {"name": "B", "icp_score": 0.3},
        {"name": "C", "icp_score": 0.5},
    ]
    result = filter_by_icp_score(prospects, min_score=0.5)
    assert len(result) == 2
    assert all(p["icp_score"] >= 0.5 for p in result)


def test_filter_no_score_field():
    prospects = [{"name": "X"}, {"name": "Y", "icp_score": 0.8}]
    result = filter_by_icp_score(prospects, min_score=0.5)
    assert len(result) == 1
    assert result[0]["name"] == "Y"
