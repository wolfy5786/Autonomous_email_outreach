#!/usr/bin/env python3
"""Deterministic plan-based scoring tests for the prospecting service."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.scoring import (  # noqa: E402
    COMPANY_DIMENSIONS,
    POC_DIMENSIONS,
    SCORING_VERSION,
    combined_score,
    semantic_search_extra,
    score_company,
    score_person,
)


def _ok(message: str) -> Tuple[bool, str]:
    return True, message


def _fail(message: str) -> Tuple[bool, str]:
    return False, message


def _plan() -> dict:
    return {
        "company_signals": [
            "industry SaaS",
            "company size 100-500",
            "funding stage growth",
            "geography United States",
            "tech stack python postgres",
            "growth hiring",
            "personalization customer story",
        ],
        "poc_signals": [
            "title CTO",
            "seniority vp",
            "department engineering",
            "technical buyer",
            "personalization founder led",
        ],
        "scoring_weights": {
            "industry_match": 0.25,
            "company_size_match": 0.1,
            "funding_stage_match": 0.1,
            "geography_match": 0.05,
            "tech_stack_match": 0.1,
            "growth_signal_match": 0.1,
            "personalization_signal_match": 0.1,
            "data_completeness": 0.1,
            "freshness": 0.1,
            "title_match": 0.2,
            "seniority_match": 0.1,
            "department_match": 0.1,
            "email_verified": 0.1,
            "linkedin_present": 0.05,
            "role_relevance": 0.15,
        },
    }


def _company() -> dict:
    return {
        "name": "Acme SaaS",
        "domain": "acme.example",
        "industry": "SaaS",
        "employee_count": 120,
        "funding_stage": "growth",
        "headquarters": {"city": "San Francisco", "country": "United States"},
        "tech_stack": ["python", "postgres", "docker"],
        "description": "Customer story driven SaaS platform with active hiring",
        "linkedin_url": "https://linkedin.com/company/acme",
        "website_url": "https://acme.example",
        "freshness_timestamp": "2026-05-10T00:00:00Z",
        "data_completeness": 0.9,
        "extra": {
            "hiring_velocity": "strong",
            "customer_story": "enterprise expansion",
        },
    }


def _person() -> dict:
    return {
        "company_id": "company-1",
        "name": "Jane Doe",
        "title": "CTO",
        "seniority": "vp",
        "department": "engineering",
        "email": "jane@example.com",
        "email_verified": True,
        "linkedin_url": "https://linkedin.com/in/jane-doe",
        "extra": {
            "role": "technical buyer",
        },
    }


def test_deterministic_plan_based_scoring() -> Tuple[bool, str]:
    try:
        plan = _plan()
        company_one = score_company(_company(), plan)
        company_two = score_company(_company(), plan)
        person_one = score_person(_person(), plan)
        person_two = score_person(_person(), plan)

        if company_one != company_two or person_one != person_two:
            return _fail("scoring was not deterministic for the same input")
        if company_one.scoring_version != SCORING_VERSION or person_one.scoring_version != SCORING_VERSION:
            return _fail("scoring version was not set to v1")
        if company_one.score <= 0.0 or person_one.score <= 0.0:
            return _fail("expected positive scores for the seeded plan and entity data")
        if combined_score(company_one, person_one) != round(0.65 * company_one.score + 0.35 * person_one.score, 6):
            return _fail("combined score did not use the requested weighting")

        expected_company_dims = set(COMPANY_DIMENSIONS)
        expected_person_dims = set(POC_DIMENSIONS)
        if set(company_one.dimension_scores) != expected_company_dims:
            return _fail("company dimensions did not match the expected set")
        if set(person_one.dimension_scores) != expected_person_dims:
            return _fail("POC dimensions did not match the expected set")

        for name, result in {**company_one.dimension_scores, **person_one.dimension_scores}.items():
            if not (0.0 <= result.score <= 1.0):
                return _fail(f"dimension {name} had an invalid score")
            if not (0.0 <= result.confidence <= 1.0):
                return _fail(f"dimension {name} had an invalid confidence")
            if not result.reason:
                return _fail(f"dimension {name} did not include a reason")

        return _ok("Plan-based scoring is deterministic and fully described")
    except Exception as exc:
        return _fail(f"deterministic scoring test failed: {exc}")


def test_semantic_fallback_and_missing_fields() -> Tuple[bool, str]:
    try:
        plan = _plan()
        company = {
            "name": "Fallback Corp",
            "extra": {
                "vertical": "SaaS",
                "headcount": "120",
                "geo": "United States",
                "stack": "python postgres",
                "growth_notes": "active hiring",
                "customer_story": "customer story",
            },
        }
        person = {
            "company_id": "company-2",
            "extra": {
                "title": "CTO",
                "seniority": "vp",
                "department": "engineering",
                "role": "technical buyer",
                "linkedin_url": "https://linkedin.com/in/fallback",
            },
        }

        company_result = score_company(company, plan)
        person_result = score_person(person, plan)

        if company_result.score <= 0.0:
            return _fail("company semantic fallback did not produce a score")
        if person_result.score <= 0.0:
            return _fail("person semantic fallback did not produce a score")

        if "extra['vertical']" not in company_result.dimension_scores["industry_match"].reason:
            return _fail("company semantic fallback did not mention the matched extra key/value")
        if "extra['title']" not in person_result.dimension_scores["title_match"].reason:
            return _fail("person semantic fallback did not mention the matched extra key/value")

        return _ok("Missing fields are handled via semantic fallback on extra data")
    except Exception as exc:
        return _fail(f"semantic fallback test failed: {exc}")


def test_semantic_search_helper() -> Tuple[bool, str]:
    try:
        record = {
            "extra": {
                "open_roles": "Hiring Kubernetes platform engineers",
                "irrelevant": "coffee mugs",
            }
        }
        match = semantic_search_extra(record, "kubernetes platform engineers hiring", "companies", "campaign-1")
        if match is None:
            return _fail("semantic_search_extra did not return a match for relevant extra data")
        if match.matched_key != "open_roles":
            return _fail("semantic_search_extra matched the wrong extra key")
        if match.matched_value != "Hiring Kubernetes platform engineers":
            return _fail("semantic_search_extra did not return the matched value")
        if match.similarity <= 0.35:
            return _fail("semantic_search_extra returned a low similarity match")
        if "open_roles" not in match.reason or "Hiring Kubernetes platform engineers" not in match.reason:
            return _fail("semantic_search_extra reason did not mention the matched key/value")

        no_match = semantic_search_extra(record, "completely unrelated query", "companies", "campaign-1")
        if no_match is not None:
            return _fail("low similarity semantic results should be ignored")

        return _ok("semantic_search_extra returns matched key/value and ignores low similarity results")
    except Exception as exc:
        return _fail(f"semantic_search_extra test failed: {exc}")


def main() -> int:
    print("\n" + "=" * 50)
    print("PLAN SCORING TESTS")
    print("=" * 50 + "\n")

    tests = [
        ("Deterministic Scoring", test_deterministic_plan_based_scoring),
        ("Semantic Fallback", test_semantic_fallback_and_missing_fields),
        ("Semantic Search Helper", test_semantic_search_helper),
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
        print("All plan scoring tests passed!")
        return 0

    print("Some plan scoring tests failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
