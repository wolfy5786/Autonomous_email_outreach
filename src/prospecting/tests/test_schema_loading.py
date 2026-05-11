#!/usr/bin/env python3
"""Seeded schema and Mongo loading test for prospecting."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Tuple

from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Mongo, MongoConfig
from app.worker import ProspectingWorker
from app.contracts import ProspectingCompletedEvent, SourcingCompletedEvent


def _seed(db) -> None:
    db.campaigns.delete_many({})
    db.plans.delete_many({})
    db.companies.delete_many({})
    db.persons.delete_many({})

    db.campaigns.insert_one(
        {
            "_id": "campaign-001",
            "name": "Seed Campaign",
            "status": "running",
            "config": {"min_icp_score": 0.0},
            "plan_id": "plan-001",
        }
    )
    db.plans.insert_one(
        {
            "_id": "plan-001",
            "campaign_id": "campaign-001",
            "company_signals": ["industry SaaS", "company size 100-500", "growth hiring"],
            "poc_signals": ["title CTO", "department engineering", "technical buyer"],
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
                "scoring_version": 0.0,
            },
        }
    )
    db.companies.insert_one(
        {
            "_id": "company-001",
            "name": "Acme SaaS",
            "industry": "SaaS",
            "employees": 120,
            "campaign_ids": ["campaign-001"],
        }
    )
    db.persons.insert_one(
        {
            "_id": "person-001",
            "company_id": "company-001",
            "name": "Jane Doe",
            "title": "CTO",
            "email": "jane@example.com",
            "campaign_ids": ["campaign-001"],
        }
    )


def test_schema_and_loading() -> Tuple[bool, str]:
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DB", "email_outreach")
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    mongo: Mongo | None = None
    try:
        db = client[db_name]
        _seed(db)

        mongo = Mongo(MongoConfig(uri=uri, db_name=db_name))
        mongo.connect()
        worker = ProspectingWorker(mongo=mongo, default_min_icp_score=0.0)

        sourcing_event = SourcingCompletedEvent.model_validate(
            {
                "campaign_id": "campaign-001",
                "entity_ids": ["company-001"],
            }
        )
        output = ProspectingCompletedEvent.model_validate(worker.handle_sourcing_completed(sourcing_event.model_dump(mode="json")))

        if output.campaign_id != "campaign-001":
            return False, "campaign id was not preserved in output"
        if not output.ranked_prospects:
            return False, "worker did not rank the seeded prospect"

        company = db.companies.find_one({"_id": "company-001"}) or {}
        person = db.persons.find_one({"_id": "person-001"}) or {}
        if company.get("icp_fit_score") is None:
            return False, "company score was not persisted"
        if person.get("icp_poc_score") is None:
            return False, "person score was not persisted"
        if person.get("email_verified") is not True:
            return False, "person email_verified flag was not updated"
        if company.get("scoring_version") != "v1" or person.get("scoring_version") != "v1":
            return False, "scoring version was not persisted"

        return True, "Schema validation, Mongo loading, and score persistence all succeeded"
    except Exception as exc:
        return False, f"Schema/loading test failed: {exc}"
    finally:
        try:
            if mongo is not None:
                mongo.close()
        finally:
            client.close()


def main() -> int:
    print("\n" + "=" * 50)
    print("SCHEMA + MONGO LOADING TEST")
    print("=" * 50 + "\n")
    passed, message = test_schema_and_loading()
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"{status}: Schema + Mongo Loading")
    print(f"  {message}\n")
    print("=" * 50)
    if passed:
        print("Schema + Mongo loading test passed!")
        return 0
    print("Schema + Mongo loading test failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())