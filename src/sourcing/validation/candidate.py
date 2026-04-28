"""
Candidate validation gate — between Phase 1 (discovery) and Phase 2 (enrichment).

Implements the separation described in ``data_sourcing_map.md``: Tier B signal sources
must be cross-checked before deep crawl/LLM spend.
"""

from __future__ import annotations

from typing import Any

from shared.models.plan import PlanRecord


def validate_candidates(
    candidates: list[dict[str, Any]],
    plan: PlanRecord,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Partition raw discovery candidates into accepted vs rejected.

    When implemented, this gate should:

    - **ICP relevance** — keyword, industry, stage, geography vs Plan Document
      (deterministic rules or small classifier; threshold per campaign).
    - **Deduplication** — same normalized ``domain`` or strong name+location match → merge or skip.
    - **Domain sanity** — valid TLD, not parking; optional MX check per plan.
    - **Blocklist** — competitors, excluded industries, sanctioned regions if configured.
    - **Tier B handling** — candidates from ``hacker_news``, ``linkedin_company``, etc. must be
      cross-validated against a Tier A directory signal before enrichment (per sourcing map).

    :param candidates: Raw dicts from ``DiscoveryResult.candidates`` (may include ``source_tier``).
    :param plan: Active plan for ICP / signal constraints.
    :returns: ``(accepted, rejected)`` — rejected entries should carry a ``reject_reason`` when implemented.

    :raises NotImplementedError: Stub until validation rules are wired.
    """
    raise NotImplementedError(
        "validate_candidates: implement ICP filter, dedup, domain sanity, blocklist, "
        "and Tier-B→Tier-A cross-check before enrichment."
    )
