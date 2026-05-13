#!/usr/bin/env python3
"""Integration test - executes prospecting scoring flow against MongoDB."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Tuple

from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Mongo, MongoConfig
from app.scoring import combined_score, score_company, score_person
from app.worker import ProspectingWorker


CAMPAIGN_ID = "test-campaign-001"
PLAN_ID = "plan-test-campaign-001"
GOOD_COMPANY_ID = "company-test-good"
BAD_COMPANY_ID = "company-test-bad"
GOOD_PERSON_ID = "person-test-good"
BAD_PERSON_ID = "person-test-bad"


def setup_test_data() -> Tuple[bool, str]:
    """Set up deterministic campaign, plan, company, and person records."""
    client: MongoClient | None = None
    try:
        uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        db_name = os.getenv("MONGODB_DB", "email_outreach")

        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        db = client[db_name]

        db.campaigns.delete_many({"_id": {"$in": [CAMPAIGN_ID]}})
        db.plans.delete_many({"_id": {"$in": [PLAN_ID]}})
        db.companies.delete_many({"_id": {"$in": [GOOD_COMPANY_ID, BAD_COMPANY_ID]}})
        db.persons.delete_many({"_id": {"$in": [GOOD_PERSON_ID, BAD_PERSON_ID]}})

        db.campaigns.insert_one(
            {
                "_id": CAMPAIGN_ID,
                "id": CAMPAIGN_ID,
                "name": "Test Campaign",
                "plan_id": PLAN_ID,
                "config": {
                    "min_icp_score": 0.6,
                },
                "status": "active",
            }
        )

        db.plans.insert_one(
            {
                "_id": PLAN_ID,
                "id": PLAN_ID,
                "campaign_id": CAMPAIGN_ID,
                "company_signals": [
                    "industry healthcare software",
                    "company size 50-250",
                    "funding stage seed",
                    "geography united states",
                    "tech stack python fastapi kubernetes",
                    "growth hiring",
                ],
                "poc_signals": [
                    "title head of growth",
                    "seniority director",
                    "department growth marketing",
                    "role outbound demand generation",
                ],
                "scoring_weights": {},
            }
        )

        db.companies.insert_many(
            [
                {
                    "_id": GOOD_COMPANY_ID,
                    "id": GOOD_COMPANY_ID,
                    "name": "MediFlow AI",
                    "domain": "mediflow.ai",
                    "industry": "healthcare software",
                    "employee_count": 140,
                    "funding_stage": "seed",
                    "location": "united states",
                    "tech_stack": "python fastapi kubernetes",
                    "description": "AI outreach workflow for healthcare teams",
                    "linkedin_url": "https://www.linkedin.com/company/mediflow-ai",
                    "website_url": "https://mediflow.ai",
                    "freshness_timestamp": 1715400000,
                },
                {
                    "_id": BAD_COMPANY_ID,
                    "id": BAD_COMPANY_ID,
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
        )

        db.persons.insert_many(
            [
                {
                    "_id": GOOD_PERSON_ID,
                    "id": GOOD_PERSON_ID,
                    "company_id": GOOD_COMPANY_ID,
                    "name": "Rina Vora",
                    "title": "head of growth",
                    "seniority": "director",
                    "department": "growth marketing",
                    "email": "rina@mediflow.ai",
                    "email_verified": False,
                    "linkedin_url": "https://www.linkedin.com/in/rina-vora",
                },
                {
                    "_id": BAD_PERSON_ID,
                    "id": BAD_PERSON_ID,
                    "company_id": BAD_COMPANY_ID,
                    "name": "Lars Holt",
                    "title": "finance controller",
                    "seniority": "manager",
                    "department": "finance",
                    "email_verified": False,
                },
            ]
        )

        return True, "Test data set up successfully"
    except Exception as exc:
        return False, f"Failed to set up test data: {exc}"
    finally:
        if client is not None:
            client.close()


def run_prospecting_worker() -> Tuple[bool, str]:
    """Run the worker directly and capture deterministic scoring output."""
    mongo: Mongo | None = None
    try:
        uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        db_name = os.getenv("MONGODB_DB", "email_outreach")

        mongo = Mongo(MongoConfig(uri=uri, db_name=db_name))
        mongo.connect()
        campaign_doc = mongo.get_campaign(CAMPAIGN_ID)
        plan_doc = mongo.get_plan(CAMPAIGN_ID)
        companies = {c.get("id"): c for c in mongo.get_companies([GOOD_COMPANY_ID, BAD_COMPANY_ID])}
        persons = {p.get("id"): p for p in mongo.get_persons_for_companies([GOOD_COMPANY_ID, BAD_COMPANY_ID])}

        good_company = companies.get(GOOD_COMPANY_ID)
        bad_company = companies.get(BAD_COMPANY_ID)
        good_person = persons.get(GOOD_PERSON_ID)
        bad_person = persons.get(BAD_PERSON_ID)
        if not campaign_doc or not plan_doc or not good_company or not bad_company or not good_person or not bad_person:
            return False, "required seed documents are missing before worker execution"

        good_total = combined_score(score_company(good_company, plan_doc), score_person(good_person, plan_doc))
        bad_total = combined_score(score_company(bad_company, plan_doc), score_person(bad_person, plan_doc))
        if good_total <= bad_total:
            return False, f"seed quality invalid: expected good score > bad score, got good={good_total}, bad={bad_total}"

        # Pick a threshold strictly between good and bad to make inclusion/exclusion deterministic.
        dynamic_min = round((good_total + bad_total) / 2, 6)
        mongo.campaigns.update_one(
            {"$or": [{"id": CAMPAIGN_ID}, {"_id": CAMPAIGN_ID}]},
            {"$set": {"config.min_icp_score": dynamic_min}},
        )

        worker = ProspectingWorker(mongo=mongo, default_min_icp_score=0.0)

        payload = worker.handle_prospecting_requested(
            {
                "campaign_id": CAMPAIGN_ID,
                "plan_id": PLAN_ID,
                "entity_ids": [GOOD_COMPANY_ID, BAD_COMPANY_ID],
                "event_id": "evt-integration-001",
            }
        )

        ranked = payload.get("ranked_prospects", [])
        if not isinstance(ranked, list):
            return False, "worker output ranked_prospects is not a list"

        included_ids = {p.get("poc_id") for p in ranked}
        if GOOD_PERSON_ID not in included_ids:
            return False, "high-fit prospect was not included after scoring"
        if BAD_PERSON_ID in included_ids:
            return False, "low-fit prospect should have been filtered by min_icp_score"

        return True, f"Worker ranked {len(ranked)} prospects and applied min_icp_score filtering"
    except Exception as exc:
        return False, f"Failed to run prospecting worker: {exc}"
    finally:
        if mongo is not None:
            mongo.close()


def verify_persistence_behavior() -> Tuple[bool, str]:
    """Verify score persistence and campaign-scoped score records in MongoDB."""
    client: MongoClient | None = None
    try:
        uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        db_name = os.getenv("MONGODB_DB", "email_outreach")

        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        db = client[db_name]

        company = db.companies.find_one({"_id": GOOD_COMPANY_ID}) or {}
        person = db.persons.find_one({"_id": GOOD_PERSON_ID}) or {}

        if company.get("icp_fit_score") is None:
            return False, "company icp_fit_score was not persisted"
        if person.get("icp_poc_score") is None:
            return False, "person icp_poc_score was not persisted"

        company_scoped = ((company.get("prospecting_scores") or {}).get(CAMPAIGN_ID) or {})
        person_scoped = ((person.get("prospecting_scores") or {}).get(CAMPAIGN_ID) or {})
        if company_scoped.get("icp_fit_score") is None:
            return False, "company campaign-scoped score is missing"
        if person_scoped.get("icp_poc_score") is None:
            return False, "person campaign-scoped score is missing"

        if person.get("email_verified") is not True:
            return False, "person email_verified was not updated to true when email existed"

        return True, "Score persistence and email_verified side-effect are correct"
    except Exception as exc:
        return False, f"Failed persistence verification: {exc}"
    finally:
        if client is not None:
            client.close()


def main() -> int:
    """Run integration tests."""
    print("\n" + "=" * 50)
    print("INTEGRATION TESTS")
    print("=" * 50 + "\n")

    tests: list[tuple[str, Any]] = [
        ("Set Up Test Data", setup_test_data),
        ("Run Prospecting Worker", run_prospecting_worker),
        ("Verify Persistence", verify_persistence_behavior),
    ]

    all_passed = True
    for test_name, test_func in tests:
        passed, message = test_func()
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
        print(f"  {message}\n")
        if not passed:
            all_passed = False

    print("=" * 50)
    if all_passed:
        print("All integration tests passed!")
        return 0

    print("Some integration tests failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
