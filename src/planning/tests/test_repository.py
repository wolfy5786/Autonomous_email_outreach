from datetime import datetime, timezone
from uuid import uuid4

import pytest
from mongomock_motor import AsyncMongoMockClient

from planning.repository import PlanRepository
from planning.schemas import LLMUsage, PlanRecord


@pytest.fixture
def repo(monkeypatch: pytest.MonkeyPatch) -> PlanRepository:
    # Swap the Motor client for mongomock before __init__ creates one.
    monkeypatch.setattr(
        "planning.repository.AsyncIOMotorClient", lambda *_args, **_kwargs: AsyncMongoMockClient()
    )
    return PlanRepository("mongodb://fake", "test_db")


def _plan(valid_llm_output_dict: dict, campaign_id: str) -> PlanRecord:
    return PlanRecord(
        id=uuid4(),
        campaign_id=campaign_id,
        created_at=datetime.now(timezone.utc),
        llm_model="gemini/gemini-1.5-pro",
        llm_usage=LLMUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        **valid_llm_output_dict,
    )


async def test_bootstrap_and_save_plan(repo: PlanRepository, valid_llm_output_dict: dict) -> None:
    await repo.bootstrap_indexes()
    plan = _plan(valid_llm_output_dict, "c1")
    await repo.save_plan(plan)

    found = await repo.find_existing_plan_id("c1")
    assert found == str(plan.id)


async def test_get_campaign_by_id_and_by_field(repo: PlanRepository) -> None:
    # Seed a campaign using _id convention.
    await repo.db["campaigns"].insert_one(
        {
            "_id": "c1",
            "id": "c1",
            "icp": {"industry": "saas"},
            "product_profile": {"name": "thing"},
        }
    )
    c = await repo.get_campaign("c1")
    assert c is not None
    assert c.id == "c1"
    assert c.icp == {"industry": "saas"}

    # Missing campaign → None.
    assert await repo.get_campaign("nope") is None


async def test_attach_plan_to_campaign(repo: PlanRepository) -> None:
    await repo.db["campaigns"].insert_one({"_id": "c1", "id": "c1", "icp": {}, "product_profile": {}})
    await repo.attach_plan_to_campaign("c1", "plan-1")
    doc = await repo.db["campaigns"].find_one({"_id": "c1"})
    assert doc["plan_id"] == "plan-1"
