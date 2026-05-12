"""Tests for ``shared.models.trace_event.TraceEvent``: round-trips via mongomock-motor."""

from __future__ import annotations

import pytest_asyncio
from beanie import init_beanie
from mongomock_motor import AsyncMongoMockClient

from shared.models import TraceEvent, TracePhase


@pytest_asyncio.fixture
async def db():
    """Fresh in-memory Mongo per test, with Beanie initialized for TraceEvent."""
    client = AsyncMongoMockClient()
    database = client["test_db"]
    await init_beanie(database=database, document_models=[TraceEvent])
    return database


async def test_trace_event_round_trip(db):
    """Inserting and re-reading a TraceEvent preserves all populated fields."""
    event = TraceEvent(
        trace_id="trace-1",
        campaign_id="camp-1",
        service="planning",
        event_name="plan.requested.consume",
        phase=TracePhase.START,
    )
    await event.insert()

    loaded = await TraceEvent.find_one(TraceEvent.trace_id == "trace-1")
    assert loaded is not None
    assert loaded.trace_id == "trace-1"
    assert loaded.campaign_id == "camp-1"
    assert loaded.service == "planning"
    assert loaded.event_name == "plan.requested.consume"
    assert loaded.phase is TracePhase.START
    assert loaded.timestamp is not None
    assert loaded.duration_ms is None
    assert loaded.error_type is None
    assert loaded.error_message is None
    assert loaded.metadata == {}


async def test_trace_event_with_end_phase_and_metadata(db):
    """END events carry duration_ms; metadata stores free-form context."""
    event = TraceEvent(
        trace_id="trace-2",
        campaign_id="camp-2",
        service="messaging",
        event_name="messaging.requested.consume",
        phase=TracePhase.END,
        duration_ms=1234,
        metadata={"queue": "messaging.requested", "retry_count": 0},
    )
    await event.insert()

    loaded = await TraceEvent.find_one(TraceEvent.trace_id == "trace-2")
    assert loaded.phase is TracePhase.END
    assert loaded.duration_ms == 1234
    assert loaded.metadata == {"queue": "messaging.requested", "retry_count": 0}


async def test_trace_event_error_phase_carries_error_fields(db):
    """ERROR events should preserve error_type and error_message round-trip."""
    event = TraceEvent(
        trace_id="trace-3",
        service="sourcing",
        event_name="discovery.run",
        phase=TracePhase.ERROR,
        duration_ms=42,
        error_type="TimeoutError",
        error_message="LLM request exceeded 30s",
    )
    await event.insert()

    loaded = await TraceEvent.find_one(TraceEvent.trace_id == "trace-3")
    assert loaded.phase is TracePhase.ERROR
    assert loaded.error_type == "TimeoutError"
    assert loaded.error_message == "LLM request exceeded 30s"
    assert loaded.campaign_id is None  # not all traces are campaign-bound


async def test_trace_event_emit_phase_for_oneshot_events(db):
    """EMIT events have no duration; used for instantaneous moments."""
    event = TraceEvent(
        trace_id="trace-4",
        campaign_id="camp-4",
        service="gateway",
        event_name="campaign.created",
        phase=TracePhase.EMIT,
        metadata={"user_id": "u-1"},
    )
    await event.insert()

    loaded = await TraceEvent.find_one(TraceEvent.trace_id == "trace-4")
    assert loaded.phase is TracePhase.EMIT
    assert loaded.duration_ms is None


async def test_trace_event_collection_is_named_trace_events(db):
    """The Beanie Settings.name must match the documented collection name."""
    assert TraceEvent.Settings.name == "trace_events"


async def test_query_campaign_timeline_returns_events_in_order(db):
    """campaign_timeline index should support ordered queries by timestamp for a campaign."""
    from datetime import datetime, timezone

    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    events = [
        TraceEvent(
            trace_id=f"t-{i}",
            campaign_id="camp-X",
            service="planning",
            event_name=f"evt.{i}",
            phase=TracePhase.EMIT,
            timestamp=base.replace(second=i),
        )
        for i in range(3)
    ]
    for e in events:
        await e.insert()

    timeline = await (
        TraceEvent.find(TraceEvent.campaign_id == "camp-X")
        .sort("+timestamp")
        .to_list()
    )
    assert [e.event_name for e in timeline] == ["evt.0", "evt.1", "evt.2"]
