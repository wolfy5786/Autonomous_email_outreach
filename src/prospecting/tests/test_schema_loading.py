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
    db.prospecting_runs.delete_many({})

    db.campaigns.insert_one(
        {
            "_id": "campaign-001",
            "name": "Seed Campaign",
            "status": "running",
            "config": {"min_icp_score": 0.0, "plan_id": "plan-001"},
            "plan_id": "plan-001",
        }
    )
    db.plans.insert_one(
        {
            "_id": "plan-001",
            "campaign_id": "campaign-001",
            "scoring_weights": {"industry": 0.6, "title": 0.4},
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
                "event_id": "evt-001",
                "schema_version": 1,
                "campaign_id": "campaign-001",
                "plan_id": "plan-001",
                "trace_id": "trace-001",
                "idempotency_key": "idemp-001",
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
        run = db.prospecting_runs.find_one({"idempotency_key": "idemp-001"}) or {}

        if company.get("campaign_scores", {}).get("campaign-001", {}).get("icp_fit_score") is None:
            return False, "campaign-scoped company score was not persisted"
        if person.get("campaign_scores", {}).get("campaign-001", {}).get("icp_poc_score") is None:
            return False, "campaign-scoped person score was not persisted"
        if run.get("status") != "completed":
            return False, "prospecting_runs record was not completed"

        return True, "Schema validation, Mongo loading, and run persistence all succeeded"
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