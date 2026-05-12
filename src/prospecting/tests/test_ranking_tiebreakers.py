#!/usr/bin/env python3
"""Deterministic tie-breaker ordering test for prospect ranking."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Tuple
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
    """Create prospects with equal total scores but varying tie-breaker fields and assert deterministic ordering."""
    try:
        # prepare three companies with identical scoring values but different data_completeness and freshness
        companies = [
            {"id": "company-a", "freshness_timestamp": 100, "extra": {}},
            {"id": "company-b", "freshness_timestamp": 50, "extra": {}},
            {"id": "company-c", "freshness_timestamp": 75, "extra": {}},
        ]

        # persons mapped to companies; vary email_verified to hit that tie-breaker
        persons = [
            {"id": "person-1", "company_id": "company-a", "email_verified": False},
            {"id": "person-2", "company_id": "company-b", "email_verified": True},
            {"id": "person-3", "company_id": "company-c", "email_verified": True},
        ]

        fake_mongo = FakeMongo(companies=companies, persons=persons, plan={"scoring_weights": {}})

        worker = ProspectingWorker(mongo=fake_mongo, default_min_icp_score=0.0)

        # monkeypatch scoring functions to return identical overall scores but expose per-dimension differences
        import app.scoring as scoring_mod  # noqa: E402

        orig_score_company = scoring_mod.score_company
        orig_score_person = scoring_mod.score_person

        try:
            # Companies: same overall score but different data_completeness dimension
            def fake_score_company(company, plan):
                dc = 0.6 if company.get("id") == "company-a" else (0.6 if company.get("id") == "company-b" else 0.6)
                dims = {k: _make_dim(0.0) for k in scoring_mod.COMPANY_DIMENSIONS}
                dims["data_completeness"] = _make_dim(0.6 if company.get("id") == "company-a" else (0.5 if company.get("id") == "company-b" else 0.5))
                # freshness not used for score here; keep equal
                return ScoringResult(score=0.7, dimension_scores=dims, scoring_version=scoring_mod.SCORING_VERSION)

            # Persons: same overall score but email_verified dimension varies
            def fake_score_person(person, plan):
                dims = {k: _make_dim(0.0) for k in scoring_mod.POC_DIMENSIONS}
                dims["email_verified"] = _make_dim(1.0 if person.get("email_verified") else 0.0)
                return ScoringResult(score=0.7, dimension_scores=dims, scoring_version=scoring_mod.SCORING_VERSION)

            scoring_mod.score_company = fake_score_company
            scoring_mod.score_person = fake_score_person

            msg = {"campaign_id": "test-campaign", "entity_ids": [c["id"] for c in companies]}
            out_json = worker.handle_sourcing_completed(msg)
            payload = json.loads(out_json)

            ranked = payload.get("ranked_prospects", [])
            # Expect person-2 (email_verified True) to appear before person-1 (False)
            ids = [r.get("poc_id") for r in ranked]
            if "person-2" not in ids or "person-1" not in ids:
                return _fail("expected person ids missing from ranked prospects")

            # person-2 should rank before person-1 because email_verified True > False
            if ids.index("person-2") >= ids.index("person-1"):
                return _fail("email_verified tie-breaker did not order prospects correctly")

            # Stability: repeated runs produce same ordering
            out_json2 = worker.handle_sourcing_completed(msg)
            payload2 = json.loads(out_json2)
            ids2 = [r.get("poc_id") for r in payload2.get("ranked_prospects", [])]
            if ids != ids2:
                return _fail("ranking was not stable across repeated runs")

            return _ok("Tie-breaker ordering is deterministic and stable")
        finally:
            scoring_mod.score_company = orig_score_company
            scoring_mod.score_person = orig_score_person

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
