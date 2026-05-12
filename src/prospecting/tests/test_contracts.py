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
    ProspectingRequestedEvent,
    RankedProspect,
)


def _ok(message: str) -> Tuple[bool, str]:
    return True, message


def _fail(message: str) -> Tuple[bool, str]:
    return False, message


def test_prospecting_requested_contract() -> Tuple[bool, str]:
    try:
        event = ProspectingRequestedEvent.model_validate(
            {
                "campaign_id": "campaign-1",
                "plan_id": "plan-1",
                "entity_ids": ["company-1", "company-2"],
            }
        )
        if event.entity_ids != ["company-1", "company-2"]:
            return _fail("entity_ids were not preserved")

        event_with_metadata = ProspectingRequestedEvent.model_validate(
            {
                "campaign_id": "campaign-1",
                "plan_id": "plan-1",
                "entity_ids": ["company-1"],
                "event_id": "evt-internal-1",
                "trace_id": "trace-internal-1",
                "idempotency_key": "idemp-internal-1",
                "scoring_version": 3,
            }
        )
        if event_with_metadata.campaign_id != "campaign-1" or event_with_metadata.entity_ids != ["company-1"]:
            return _fail("prospecting requested metadata handling failed")
        return _ok("Prospecting requested contract enforces the expected shape")
    except Exception as exc:
        return _fail(f"Prospecting requested contract failed: {exc}")


def test_prospecting_requested_requires_plan_id() -> Tuple[bool, str]:
    try:
        ProspectingRequestedEvent.model_validate(
            {
                "campaign_id": "campaign-1",
                "entity_ids": ["company-1"],
            }
        )
        return _fail("prospecting requested accepted a payload without plan_id")
    except ValidationError as exc:
        if "plan_id" not in str(exc):
            return _fail(f"unexpected validation error for missing plan_id: {exc}")
        return _ok("Prospecting requested contract requires plan_id")
    except Exception as exc:
        return _fail(f"missing plan_id contract check failed: {exc}")


def test_mongo_documents_contract() -> Tuple[bool, str]:
    try:
        company = CompanyDocument.model_validate(
            {"_id": "company-1", "name": "Acme", "employees": 42, "industry": "SaaS", "icp_fit_score": 0.82}
        )
        person = PersonDocument.model_validate(
            {
                "id": "person-1",
                "company_id": "company-1",
                "name": "Jane Doe",
                "title": "CEO",
                "email_verified": True,
                "icp_poc_score": 0.71,
            }
        )
        plan = PlanDocument.model_validate(
            {
                "_id": "plan-1",
                "campaign_id": "campaign-1",
                "company_signals": ["industry SaaS", "company size 100-500"],
                "poc_signals": ["title CTO", "department engineering"],
                "scoring_weights": {"industry_match": 0.7, "title_match": 0.3},
            }
        )

        if company.id != "company-1" or company.employee_count != 42:
            return _fail("company document normalization failed")
        if company.icp_fit_score != 0.82:
            return _fail("company score field normalization failed")
        if person.company_id != "company-1" or person.title != "CEO":
            return _fail("person document normalization failed")
        if person.email_verified is not True or person.icp_poc_score != 0.71:
            return _fail("person score / verification field normalization failed")
        if plan.id != "plan-1" or plan.scoring_weights.get("industry_match") != 0.7:
            return _fail("plan document normalization failed")
        if plan.company_signals != ["industry SaaS", "company size 100-500"]:
            return _fail("company signals were not preserved")
        if plan.poc_signals != ["title CTO", "department engineering"]:
            return _fail("poc signals were not preserved")

        return _ok("Mongo document contracts normalize the expected fields")
    except Exception as exc:
        return _fail(f"Mongo document contract failed: {exc}")


def test_output_contract() -> Tuple[bool, str]:
    try:
        payload = ProspectingCompletedEvent.model_validate(
            {
                "campaign_id": "campaign-1",
                "ranked_prospects": [
                    {
                        "rank": 1,
                        "company_id": "company-1",
                        "poc_id": "person-1",
                        "icp_fit_score": 0.8,
                        "icp_poc_score": 0.7,
                        "total_score": 0.76,
                        "scoring_version": "v1",
                        "scoring_reasons": {"company": {"industry_match": "reason"}, "poc": {"title_match": "reason"}},
                    },
                    RankedProspect(
                        rank=2,
                        company_id="company-2",
                        poc_id="person-2",
                        icp_fit_score=0.75,
                        icp_poc_score=0.6,
                        total_score=0.705,
                        scoring_version="v1",
                        scoring_reasons={},
                    ),
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
        ("Prospecting Requested Contract", test_prospecting_requested_contract),
        ("Prospecting Requested Requires Plan ID", test_prospecting_requested_requires_plan_id),
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
