#!/usr/bin/env python3
"""End-to-end scoring evaluation using deterministic seeded fixtures."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.worker import ProspectingWorker
from app.scoring import combined_score, score_company, score_person


CAMPAIGN_ID = "cmp-scoring-e2e-001"
PLAN_ID = "plan-scoring-e2e-001"


def _campaign(min_icp_score: float = 0.55, max_drafts: int | None = None) -> dict[str, Any]:
    config: dict[str, Any] = {"min_icp_score": min_icp_score}
    if max_drafts is not None:
        config["max_drafts"] = max_drafts
    return {
        "id": CAMPAIGN_ID,
        "name": "Scoring QA Campaign",
        "status": "active",
        "plan_id": PLAN_ID,
        "config": config,
    }


def _plan() -> dict[str, Any]:
    return {
        "id": PLAN_ID,
        "campaign_id": CAMPAIGN_ID,
        "company_signals": [
            "industry healthcare software",
            "company_size 50-250",
            "funding_stage seed series_a",
            "geography united states",
            "tech_stack python fastapi kubernetes",
            "growth hiring expansion funding",
            "personalization ai outreach workflow",
        ],
        "poc_signals": [
            "title head of growth",
            "seniority director vp",
            "department growth marketing revenue",
            "role outbound demand generation lifecycle",
            "personalization product launch hiring signal",
        ],
        "scoring_weights": {
            "industry_match": 1.0,
            "company_size_match": 1.0,
            "funding_stage_match": 1.0,
            "geography_match": 1.0,
            "tech_stack_match": 1.0,
            "growth_signal_match": 1.0,
            "personalization_signal_match": 1.0,
            "data_completeness": 0.0,
            "freshness": 0.0,
            "title_match": 1.0,
            "seniority_match": 1.0,
            "department_match": 1.0,
            "email_verified": 0.0,
            "linkedin_present": 1.0,
            "role_relevance": 1.0,
        },
    }


def _companies() -> list[dict[str, Any]]:
    return [
        {
            "id": "co-alpha",
            "name": "MediFlow AI",
            "domain": "mediflow.ai",
            "industry": "healthcare software",
            "employee_count": 140,
            "funding_stage": "seed",
            "location": "united states",
            "tech_stack": "python fastapi kubernetes",
            "description": "AI outreach workflow for payer-provider onboarding",
            "linkedin_url": "https://www.linkedin.com/company/mediflow-ai",
            "website_url": "https://mediflow.ai",
            "freshness_timestamp": 1715400000,
        },
        {
            "id": "co-beta",
            "name": "CareRoute",
            "domain": "careroute.io",
            "industry": "healthcare software",
            "employee_count": 180,
            "funding_stage": "series_a",
            "location": "united states",
            "tech_stack": "python fastapi kubernetes",
            "description": "Revenue-cycle orchestration for clinics",
            "linkedin_url": "https://www.linkedin.com/company/careroute",
            "website_url": "https://careroute.io",
            "freshness_timestamp": 1715300000,
        },
        {
            "id": "co-gamma",
            "name": "AdLedger X",
            "domain": "adledgerx.com",
            "industry": "adtech",
            "employee_count": 2200,
            "funding_stage": "late_stage",
            "location": "germany",
            "tech_stack": "java monolith",
            "description": "Enterprise ad exchange",
            "website_url": "https://adledgerx.com",
            "freshness_timestamp": 1715000000,
        },
    ]


def _persons() -> list[dict[str, Any]]:
    return [
        {
            "id": "p-alpha-1",
            "company_id": "co-alpha",
            "name": "Rina Vora",
            "title": "head of growth",
            "seniority": "director",
            "department": "growth marketing",
            "email": "rina@mediflow.ai",
            "email_verified": False,
            "linkedin_url": "https://www.linkedin.com/in/rina-vora",
        },
        {
            "id": "p-beta-1",
            "company_id": "co-beta",
            "name": "Ava Chen",
            "title": "head of growth",
            "seniority": "director",
            "department": "growth marketing",
            "email": "ava@careroute.io",
            "email_verified": True,
            "linkedin_url": "https://www.linkedin.com/in/ava-chen",
        },
        {
            "id": "p-gamma-1",
            "company_id": "co-gamma",
            "name": "Lars Holt",
            "title": "finance controller",
            "seniority": "manager",
            "department": "finance",
            "email_verified": False,
        },
    ]


class FakeMongo:
    def __init__(self, campaign: dict[str, Any], plan: dict[str, Any], companies: list[dict[str, Any]], persons: list[dict[str, Any]]):
        self._campaign = copy.deepcopy(campaign)
        self._plan = copy.deepcopy(plan)
        self._companies = {c["id"]: copy.deepcopy(c) for c in companies}
        self._persons = {p["id"]: copy.deepcopy(p) for p in persons}

    def get_campaign(self, campaign_id: str) -> dict[str, Any] | None:
        if campaign_id != self._campaign.get("id"):
            return None
        return copy.deepcopy(self._campaign)

    def get_plan(self, campaign_id: str) -> dict[str, Any] | None:
        if campaign_id != self._campaign.get("id"):
            return None
        return copy.deepcopy(self._plan)

    def get_companies(self, company_ids: list[str]) -> list[dict[str, Any]]:
        return [copy.deepcopy(self._companies[cid]) for cid in company_ids if cid in self._companies]

    def get_persons_for_companies(self, company_ids: list[str]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for person in self._persons.values():
            if person.get("company_id") in company_ids:
                out.append(copy.deepcopy(person))
        return out

    def update_company_score(
        self,
        company_id: str,
        campaign_id: str,
        score: float,
        scoring_version: str,
        scored_at: str | None = None,
        reasons: dict[str, Any] | None = None,
        event_id: str | None = None,
    ) -> None:
        company = self._companies.get(company_id)
        if company is None:
            return
        company["icp_fit_score"] = score
        company["scoring_version"] = scoring_version
        company.setdefault("prospecting_scores", {})[campaign_id] = {
            "icp_fit_score": score,
            "scoring_version": scoring_version,
            "scored_at": scored_at,
            "event_id": event_id,
            "reasons": reasons or {},
        }

    def update_person_score(
        self,
        person_id: str,
        campaign_id: str,
        score: float,
        scoring_version: str,
        scored_at: str | None = None,
        reasons: dict[str, Any] | None = None,
        event_id: str | None = None,
    ) -> None:
        person = self._persons.get(person_id)
        if person is None:
            return
        person["icp_poc_score"] = score
        person["scoring_version"] = scoring_version
        person.setdefault("prospecting_scores", {})[campaign_id] = {
            "icp_poc_score": score,
            "scoring_version": scoring_version,
            "scored_at": scored_at,
            "event_id": event_id,
            "reasons": reasons or {},
        }

    def update_person_email_verified(self, person_id: str, verified: bool) -> None:
        person = self._persons.get(person_id)
        if person is None:
            return
        person["email_verified"] = verified


def _ok(message: str) -> Tuple[bool, str]:
    return True, message


def _fail(message: str) -> Tuple[bool, str]:
    return False, message


def _run_worker(mongo: FakeMongo, entity_ids: list[str], event_id: str) -> dict[str, Any]:
    worker = ProspectingWorker(mongo=mongo, default_min_icp_score=0.0)
    return worker.handle_prospecting_requested(
        {
            "campaign_id": CAMPAIGN_ID,
            "plan_id": PLAN_ID,
            "entity_ids": entity_ids,
            "event_id": event_id,
        }
    )


def test_ranking_and_threshold() -> Tuple[bool, str]:
    try:
        plan = _plan()
        companies = _companies()
        persons = _persons()
        companies_by_id = {c["id"]: c for c in companies}
        persons_by_id = {p["id"]: p for p in persons}

        alpha_total = combined_score(
            score_company(companies_by_id["co-alpha"], plan),
            score_person(persons_by_id["p-alpha-1"], plan),
        )
        gamma_total = combined_score(
            score_company(companies_by_id["co-gamma"], plan),
            score_person(persons_by_id["p-gamma-1"], plan),
        )
        if alpha_total <= gamma_total:
            return _fail(
                f"seed quality invalid: expected alpha score > gamma score, got alpha={alpha_total}, gamma={gamma_total}"
            )

        threshold = round((alpha_total + gamma_total) / 2, 6)
        mongo = FakeMongo(_campaign(min_icp_score=threshold), plan, companies, persons)
        payload = _run_worker(mongo, ["co-alpha", "co-beta", "co-gamma"], "evt-e2e-001")
        ranked = payload.get("ranked_prospects", [])
        ids = [r.get("poc_id") for r in ranked]

        if "p-gamma-1" in ids:
            return _fail("low-fit prospect p-gamma-1 should be filtered by min_icp_score")
        if not ids:
            return _fail("expected at least one ranked prospect")
        if ids[0] != "p-alpha-1":
            return _fail(f"expected p-alpha-1 to rank first, got {ids[0]!r}")

        return _ok("Ranking sanity and threshold filtering passed")
    except Exception as exc:
        return _fail(f"ranking and threshold test failed: {exc}")


def test_max_drafts_cap() -> Tuple[bool, str]:
    try:
        mongo = FakeMongo(_campaign(min_icp_score=0.0, max_drafts=1), _plan(), _companies(), _persons())
        payload = _run_worker(mongo, ["co-alpha", "co-beta", "co-gamma"], "evt-e2e-002")
        ranked = payload.get("ranked_prospects", [])

        if len(ranked) != 1:
            return _fail(f"expected exactly 1 ranked prospect with max_drafts=1, got {len(ranked)}")

        return _ok("max_drafts cap is enforced")
    except Exception as exc:
        return _fail(f"max_drafts test failed: {exc}")


def test_deterministic_output() -> Tuple[bool, str]:
    try:
        mongo_a = FakeMongo(_campaign(min_icp_score=0.55), _plan(), _companies(), _persons())
        mongo_b = FakeMongo(_campaign(min_icp_score=0.55), _plan(), _companies(), _persons())

        payload_a = _run_worker(mongo_a, ["co-alpha", "co-beta", "co-gamma"], "evt-e2e-003")
        payload_b = _run_worker(mongo_b, ["co-alpha", "co-beta", "co-gamma"], "evt-e2e-003")

        if payload_a != payload_b:
            return _fail("same seed input produced different output payloads")

        return _ok("deterministic output check passed")
    except Exception as exc:
        return _fail(f"deterministic output test failed: {exc}")


def main() -> int:
    print("\n" + "=" * 50)
    print("E2E SCORING EVALUATION")
    print("=" * 50 + "\n")

    tests = [
        ("Ranking + Threshold", test_ranking_and_threshold),
        ("Max Drafts Cap", test_max_drafts_cap),
        ("Deterministic Output", test_deterministic_output),
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
        print("All E2E scoring evaluation tests passed!")
        return 0

    print("Some E2E scoring evaluation tests failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
