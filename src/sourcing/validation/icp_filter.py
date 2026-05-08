"""Filter prospects by ICP score threshold."""
from typing import Any


def filter_by_icp_score(
    prospects: list[dict[str, Any]],
    min_score: float = 0.5,
) -> list[dict[str, Any]]:
    """Return only prospects meeting the minimum ICP score."""
    return [
        p for p in prospects
        if p.get("icp_score", 0) >= min_score
    ]
