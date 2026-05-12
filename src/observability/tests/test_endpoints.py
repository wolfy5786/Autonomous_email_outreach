"""Smoke tests for the observability FastAPI app — bypass lifespan, wire deps directly."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest_asyncio
from fastapi.testclient import TestClient
from shared.models import TraceEvent, TracePhase

from observability.main import app
from observability.repository import TraceRepository


@pytest_asyncio.fixture
async def client(mock_db):
    # Inject a fake mongo_client (TestClient hits /ready via Motor admin.ping —
    # use a stand-in object that returns a successful ping).
    class _FakeAdmin:
        async def command(self, _cmd: str) -> dict:
            return {"ok": 1}

    class _FakeClient:
        admin = _FakeAdmin()

        def close(self) -> None:  # pragma: no cover
            pass

    app.state.mongo_client = _FakeClient()
    app.state.repo = TraceRepository(mock_db)
    return TestClient(app)


def _insert_event(**fields) -> TraceEvent:
    defaults = {
        "trace_id": "t1",
        "campaign_id": "c-1",
        "service": "planning",
        "event_name": "plan.requested.consume",
        "phase": TracePhase.START,
        "timestamp": datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    }
    defaults.update(fields)
    return TraceEvent(**defaults)


async def test_health_returns_ok(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_returns_ok_when_mongo_pings(client: TestClient):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_api_campaigns_lists_campaign_after_inserting_event(client: TestClient):
    await _insert_event(campaign_id="c-listing").insert()
    response = client.get("/api/campaigns")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["campaign_id"] == "c-listing"
    assert payload[0]["event_count"] == 1


async def test_api_timeline_returns_404_for_unknown_campaign(client: TestClient):
    response = client.get("/api/campaigns/does-not-exist/timeline")
    assert response.status_code == 404


async def test_api_timeline_returns_events_in_order(client: TestClient):
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    await _insert_event(
        campaign_id="c-2", event_name="b", timestamp=base.replace(second=20)
    ).insert()
    await _insert_event(
        campaign_id="c-2", event_name="a", timestamp=base.replace(second=10)
    ).insert()
    response = client.get("/api/campaigns/c-2/timeline")
    assert response.status_code == 200
    names = [e["event_name"] for e in response.json()]
    assert names == ["a", "b"]


async def test_campaigns_html_page_renders_known_campaign(client: TestClient):
    await _insert_event(campaign_id="c-html").insert()
    response = client.get("/")
    assert response.status_code == 200
    assert "c-html" in response.text


async def test_timeline_html_page_renders_events(client: TestClient):
    await _insert_event(campaign_id="c-tl", service="messaging", event_name="evt").insert()
    response = client.get("/campaigns/c-tl")
    assert response.status_code == 200
    assert "evt" in response.text
    assert "messaging" in response.text
