from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Mongo, MongoConfig
from app.worker import ProspectingWorker


def _matches(doc: dict[str, Any], query: dict[str, Any]) -> bool:
    if "$or" in query:
        return any(_matches(doc, branch) for branch in query["$or"])

    for key, expected in query.items():
        if doc.get(key) != expected:
            return False
    return True


class FakeCollection:
    def __init__(self, docs: list[dict[str, Any]] | None = None):
        self.docs = docs or []
        self.queries: list[dict[str, Any]] = []

    def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        self.queries.append(query)
        for doc in self.docs:
            if _matches(doc, query):
                return doc
        return None


class FakeDB:
    def __init__(self, campaigns: list[dict[str, Any]], plans: list[dict[str, Any]]):
        self._collections = {
            "campaigns": FakeCollection(campaigns),
            "plans": FakeCollection(plans),
        }

    def __getitem__(self, name: str) -> FakeCollection:
        return self._collections[name]


class FakeMongoForWorker:
    def __init__(self, campaign: dict[str, Any] | None, plan: dict[str, Any] | None):
        self._campaign = campaign
        self._plan = plan

    def get_campaign(self, campaign_id: str) -> dict[str, Any] | None:
        return self._campaign

    def get_plan(self, campaign_id: str) -> dict[str, Any] | None:
        return self._plan

    def get_companies(self, company_ids):
        return []

    def get_persons_for_companies(self, company_ids):
        return []

    def update_company_score(self, *args, **kwargs):
        return None

    def update_person_score(self, *args, **kwargs):
        return None

    def update_person_email_verified(self, *args, **kwargs):
        return None


def test_get_campaign_finds_campaign_id() -> None:
    mongo = Mongo(MongoConfig(uri="mongodb://example", db_name="example"))
    mongo._db = FakeDB(
        campaigns=[{"campaign_id": "c-1", "status": "prospecting"}],
        plans=[],
    )

    campaign = mongo.get_campaign("c-1")

    assert campaign == {"campaign_id": "c-1", "status": "prospecting"}


def test_get_campaign_supports_legacy_id_and_object_id() -> None:
    mongo = Mongo(MongoConfig(uri="mongodb://example", db_name="example"))
    fake_db = FakeDB(
        campaigns=[
            {"id": "legacy-id", "status": "prospecting"},
            {"_id": "object-id", "status": "prospecting"},
        ],
        plans=[],
    )
    mongo._db = fake_db

    legacy = mongo.get_campaign("legacy-id")
    object_id = mongo.get_campaign("object-id")

    assert legacy == {"id": "legacy-id", "status": "prospecting"}
    assert object_id == {"_id": "object-id", "status": "prospecting"}


def test_get_plan_uses_campaign_plan_id() -> None:
    mongo = Mongo(MongoConfig(uri="mongodb://example", db_name="example"))
    fake_db = FakeDB(
        campaigns=[{"campaign_id": "c-1", "plan_id": "p-1", "status": "prospecting"}],
        plans=[{"id": "p-1", "campaign_id": "c-1", "scoring_weights": {}}],
    )
    mongo._db = fake_db

    plan = mongo.get_plan("c-1")

    assert plan == {"id": "p-1", "campaign_id": "c-1", "scoring_weights": {}}


def test_worker_accepts_campaign_with_only_campaign_id() -> None:
    worker = ProspectingWorker(
        mongo=FakeMongoForWorker(
            campaign={"campaign_id": "c-1", "plan_id": "p-1", "status": "prospecting", "config": {}},
            plan={"id": "p-1", "campaign_id": "c-1", "scoring_weights": {}},
        ),
        default_min_icp_score=0.0,
    )

    output = worker.handle_prospecting_requested({"campaign_id": "c-1", "plan_id": "p-1", "entity_ids": []})

    assert output == {"campaign_id": "c-1", "ranked_prospects": []}