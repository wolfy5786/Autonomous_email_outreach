#!/usr/bin/env python3
"""Deterministic tie-breaker ordering test for prospect ranking."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.scoring as scoring_mod  # noqa: E402
import app.worker as worker_mod  # noqa: E402
from app.worker import ProspectingWorker  # noqa: E402
from app.scoring import ScoringResult, DimensionScore  # noqa: E402


def _ok(message: str) -> Tuple[bool, str]:
    return True, message


def _fail(message: str) -> Tuple[bool, str]:
    return False, message


class FakeMongo:
    def __init__(self, companies, persons, plan=None, campaign=None):
        self._companies = companies
        self._persons = persons
        self._plan = plan or {"scoring_weights": {}}
        self._campaign = campaign or {"config": {}}

    def get_plan(self, campaign_id: str):
        return self._plan

    def get_campaign(self, campaign_id: str):
        return self._campaign

    def get_companies(self, company_ids):
        return [c for c in self._companies if c.get("id") in company_ids or c.get("_id") in company_ids]

    def get_persons_for_companies(self, company_ids):
        return [p for p in self._persons if p.get("company_id") in company_ids]

    def update_company_score(self, *args, **kwargs):
        return None

    def update_person_score(self, *args, **kwargs):
        return None

    def update_person_email_verified(self, *args, **kwargs):
        return None


def _make_dim(score: float, reason: str = "r") -> DimensionScore:
    return DimensionScore(score=score, confidence=1.0, reason=reason)


def test_tiebreaker_ordering() -> Tuple[bool, str]:
    """Create prospects with equal total scores and assert full tie-break ordering."""
    try:
        # All prospects will share the same total score, then rank by:
        # 1) company_data_completeness desc
        # 2) person_email_verified desc
        # 3) freshness_timestamp desc
        companies = [
            {"id": "company-a", "freshness_timestamp": 100, "extra": {}},
            {"id": "company-b", "freshness_timestamp": 90, "extra": {}},
            {"id": "company-c", "freshness_timestamp": 80, "extra": {}},
            {"id": "company-d", "freshness_timestamp": 70, "extra": {}},
        ]

        persons = [
            {"id": "person-1", "company_id": "company-a", "email_verified": False},
            {"id": "person-2", "company_id": "company-b", "email_verified": True},
            {"id": "person-3", "company_id": "company-c", "email_verified": True},
            {"id": "person-4", "company_id": "company-d", "email_verified": False},
        ]

        fake_mongo = FakeMongo(companies=companies, persons=persons, plan={"scoring_weights": {}})

        worker = ProspectingWorker(mongo=fake_mongo, default_min_icp_score=0.0)

        orig_score_company = worker_mod.score_company
        orig_score_person = worker_mod.score_person

        try:
            company_data_completeness = {
                "company-a": 0.9,
                "company-b": 0.8,
                "company-c": 0.8,
                "company-d": 0.7,
            }

            def fake_score_company(company, plan):
                dims = {k: _make_dim(0.0) for k in scoring_mod.COMPANY_DIMENSIONS}
                dims["data_completeness"] = _make_dim(company_data_completeness[company.get("id", "")])
                return ScoringResult(score=0.7, dimension_scores=dims, scoring_version=scoring_mod.SCORING_VERSION)

            def fake_score_person(person, plan):
                dims = {k: _make_dim(0.0) for k in scoring_mod.POC_DIMENSIONS}
                dims["email_verified"] = _make_dim(1.0 if person.get("email_verified") else 0.0)
                return ScoringResult(score=0.7, dimension_scores=dims, scoring_version=scoring_mod.SCORING_VERSION)

            worker_mod.score_company = fake_score_company
            worker_mod.score_person = fake_score_person

            msg = {"campaign_id": "test-campaign", "plan_id": "plan-1", "entity_ids": [c["id"] for c in companies]}
            payload = worker.handle_prospecting_requested(msg)

            ranked = payload.get("ranked_prospects", [])
            ids = [r.get("poc_id") for r in ranked]
            expected = ["person-1", "person-2", "person-3", "person-4"]
            if ids != expected:
                return _fail(f"unexpected tie-break order: expected {expected}, got {ids}")

            # Verify each tie-breaker condition explicitly.
            if ids.index("person-1") >= ids.index("person-2"):
                return _fail("data_completeness tie-breaker did not place person-1 first")

            if ids.index("person-2") >= ids.index("person-3"):
                return _fail("freshness tie-breaker did not place person-2 ahead of person-3")

            if ids.index("person-3") >= ids.index("person-4"):
                return _fail("data_completeness tie-breaker did not place person-3 ahead of person-4")

            # Stability: repeated runs produce same ordering
            payload2 = worker.handle_prospecting_requested(msg)
            ids2 = [r.get("poc_id") for r in payload2.get("ranked_prospects", [])]
            if ids != ids2:
                return _fail("ranking was not stable across repeated runs")

            return _ok("Tie-breaker ordering is deterministic and stable")
        finally:
            worker_mod.score_company = orig_score_company
            worker_mod.score_person = orig_score_person

    except Exception as exc:
        return _fail(f"tie-breaker test failed: {exc}")


def main() -> int:
    print("\n" + "=" * 50)
    print("TIE-BREAKER ORDERING TEST")
    print("=" * 50 + "\n")

    tests = [("Tie-breaker Determinism", test_tiebreaker_ordering)]

    all_passed = True
    for name, func in tests:
        passed, message = func()
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
        print(f"  {message}\n")
        if not passed:
            all_passed = False

    print("=" * 50)
    if all_passed:
        print("All tie-breaker tests passed!")
        return 0

    print("Some tie-breaker tests failed.")
    return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
