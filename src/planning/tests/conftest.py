import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

# Make both `planning` and `local_infrastructure` importable from tests.
_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT / "src" / "planning"))


@pytest.fixture
def sample_icp() -> dict[str, Any]:
    return {
        "industry": "B2B SaaS",
        "employee_range": [50, 500],
        "stack_includes": ["Kubernetes", "AWS"],
    }


@pytest.fixture
def sample_product() -> dict[str, Any]:
    return {
        "name": "Acme Observability",
        "value_prop": "Correlate deploys with runtime anomalies.",
    }


@pytest.fixture
def valid_llm_output_dict() -> dict[str, Any]:
    return {
        "company_signals": [
            "HQ in US or EU, 50-500 employees on LinkedIn",
            "uses Kubernetes in production (k8s manifests in public GitHub repos)",
            "Series A to Series B on Crunchbase within last 18 months",
        ],
        "poc_signals": [
            "title contains 'VP Engineering' or 'Director of Platform'",
            "tenure >= 6 months at current company",
            "located in US or EU",
        ],
        "scoring_weights": {
            "industry_match": 0.25,
            "size_match": 0.15,
            "tech_stack_match": 0.30,
            "seniority_match": 0.15,
            "title_match": 0.15,
        },
        "personalization_hooks": [
            "funding round announced in last 90 days",
            "new job postings for platform/infra roles in last 30 days",
            "recent engineering-blog post about Kubernetes",
        ],
        "email_tone": "technical",
        "email_angle": "Help platform teams cut incident response time by correlating deploys with runtime anomalies in under two minutes.",
    }


class FakeBroker:
    """Minimal MessageBroker double that records published messages."""

    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []

    async def publish(self, topic: str, message: dict[str, Any]) -> None:
        self.published.append((topic, message))

    async def subscribe(self, topic: str, handler: Any) -> None:  # pragma: no cover
        raise NotImplementedError

    async def disconnect(self) -> None:  # pragma: no cover
        pass


@pytest.fixture
def fake_broker() -> FakeBroker:
    return FakeBroker()


class FakeRepo:
    """In-memory stand-in for PlanRepository."""

    def __init__(self) -> None:
        self.campaigns: dict[str, Any] = {}
        self.plans_by_campaign: dict[str, dict[str, Any]] = {}
        self.save_raises_duplicate_on_first_call: bool = False
        self._save_call_count: int = 0
        self.attached: list[tuple[str, str]] = []

    async def get_campaign(self, campaign_id: str) -> Any:
        return self.campaigns.get(campaign_id)

    async def find_existing_plan_id(self, campaign_id: str) -> str | None:
        existing = self.plans_by_campaign.get(campaign_id)
        return existing["id"] if existing else None

    async def save_plan(self, plan: Any) -> None:
        self._save_call_count += 1
        if self.save_raises_duplicate_on_first_call and self._save_call_count == 1:
            from pymongo.errors import DuplicateKeyError
            # Simulate that another worker raced and already wrote a plan.
            self.plans_by_campaign[plan.campaign_id] = {"id": str(uuid4())}
            raise DuplicateKeyError("duplicate")
        self.plans_by_campaign[plan.campaign_id] = {"id": str(plan.id)}

    async def attach_plan_to_campaign(self, campaign_id: str, plan_id: str) -> None:
        self.attached.append((campaign_id, plan_id))


@pytest.fixture
def fake_repo() -> FakeRepo:
    return FakeRepo()


@pytest.fixture
def utcnow() -> datetime:
    return datetime.now(timezone.utc)
