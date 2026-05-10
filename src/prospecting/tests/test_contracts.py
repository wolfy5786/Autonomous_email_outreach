#!/usr/bin/env python3
"""Schema contract tests for the prospecting service."""

from __future__ import annotations

import sys
from typing import Tuple
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.contracts import (
    CompanyDocument,
    PersonDocument,
    PlanDocument,
    ProspectingCompletedEvent,
    RankedProspect,
    SourcingCompletedEvent,
)


def _ok(message: str) -> Tuple[bool, str]:
    return True, message


def _fail(message: str) -> Tuple[bool, str]:
    return False, message


def test_sourcing_event_contract() -> Tuple[bool, str]:
    try:
        event = SourcingCompletedEvent.model_validate(
            {
                "event_id": "evt-1",
                "schema_version": 1,
                "campaign_id": "campaign-1",
                "plan_id": "plan-1",
                "trace_id": "trace-1",
                "idempotency_key": "idemp-1",
                "entity_ids": ["company-1", "company-2"],
            }
        )
        if event.entity_ids != ["company-1", "company-2"]:
            return _fail("entity_ids were not preserved")

        try:
            SourcingCompletedEvent.model_validate(
                {
                    "event_id": "evt-1",
                    "schema_version": 1,
                    "campaign_id": "campaign-1",
                    "plan_id": "plan-1",
                    "trace_id": "trace-1",
                    "idempotency_key": "idemp-1",
                    "entity_ids": ["company-1"],
                    "unexpected": True,
                }
            )
            return _fail("unexpected fields should be rejected")
        except ValidationError:
            return _ok("Sourcing event contract enforces the expected shape")
    except Exception as exc:
        return _fail(f"Sourcing event contract failed: {exc}")


def test_mongo_documents_contract() -> Tuple[bool, str]:
    try:
        company = CompanyDocument.model_validate(
            {"_id": "company-1", "name": "Acme", "employees": 42, "industry": "SaaS"}
        )
        person = PersonDocument.model_validate(
            {"id": "person-1", "company_id": "company-1", "name": "Jane Doe", "title": "CEO"}
        )
        plan = PlanDocument.model_validate(
            {"_id": "plan-1", "campaign_id": "campaign-1", "scoring_weights": {"industry": 0.7}}
        )

        if company.id != "company-1" or company.employee_count != 42:
            return _fail("company document normalization failed")
        if person.company_id != "company-1" or person.title != "CEO":
            return _fail("person document normalization failed")
        if plan.id != "plan-1" or plan.scoring_weights.get("industry") != 0.7:
            return _fail("plan document normalization failed")

        return _ok("Mongo document contracts normalize the expected fields")
    except Exception as exc:
        return _fail(f"Mongo document contract failed: {exc}")


def test_output_contract() -> Tuple[bool, str]:
    try:
        payload = ProspectingCompletedEvent.model_validate(
            {
                "event_id": "evt-2",
                "schema_version": 1,
                "campaign_id": "campaign-1",
                "plan_id": "plan-1",
                "trace_id": "trace-2",
                "idempotency_key": "idemp-2",
                "ranked_prospects": [
                    {"company_id": "company-1", "poc_id": "person-1", "score": 0.91},
                    RankedProspect(company_id="company-2", poc_id="person-2", score=0.75),
                ],
            }
        )
        if len(payload.ranked_prospects) != 2:
            return _fail("ranked prospects were not validated correctly")
        return _ok("Prospecting output contract is locked")
    except Exception as exc:
        return _fail(f"Output contract failed: {exc}")


def main() -> int:
    print("\n" + "=" * 50)
    print("SCHEMA CONTRACT TESTS")
    print("=" * 50 + "\n")

    tests = [
        ("Sourcing Event Contract", test_sourcing_event_contract),
        ("Mongo Document Contract", test_mongo_documents_contract),
        ("Output Contract", test_output_contract),
    ]

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
        print("All schema contract tests passed!")
        return 0

    print("Some schema contract tests failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
