"""Tests for ``observability.repository.TraceRepository``."""

from __future__ import annotations

from datetime import datetime, timezone

from shared.models import TraceEvent, TracePhase

from observability.repository import TraceRepository


async def _insert(
    *,
    trace_id: str,
    campaign_id: str | None,
    service: str,
    event_name: str,
    phase: TracePhase,
    timestamp: datetime,
) -> None:
    event = TraceEvent(
        trace_id=trace_id,
        campaign_id=campaign_id,
        service=service,
        event_name=event_name,
        phase=phase,
        timestamp=timestamp,
    )
    await event.insert()


async def test_list_campaigns_returns_groups_with_aggregates(mock_db):
    """list_campaigns groups by campaign_id and aggregates counts/services."""
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    await _insert(
        trace_id="t1", campaign_id="c-A", service="gateway",
        event_name="campaign.created", phase=TracePhase.EMIT, timestamp=base,
    )
    await _insert(
        trace_id="t1", campaign_id="c-A", service="planning",
        event_name="plan.requested.consume", phase=TracePhase.START,
        timestamp=base.replace(second=10),
    )
    await _insert(
        trace_id="t2", campaign_id="c-B", service="planning",
        event_name="plan.requested.consume", phase=TracePhase.START,
        timestamp=base.replace(second=20),
    )

    repo = TraceRepository(mock_db)
    rows = await repo.list_campaigns()

    # Most recently active first.
    assert [r.campaign_id for r in rows] == ["c-B", "c-A"]
    by_id = {r.campaign_id: r for r in rows}
    assert by_id["c-A"].event_count == 2
    assert by_id["c-A"].services == ["gateway", "planning"]
    assert by_id["c-B"].event_count == 1


async def test_list_campaigns_excludes_events_with_no_campaign_id(mock_db):
    """Trace events lacking a campaign_id should not appear on the dashboard."""
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    await _insert(
        trace_id="t-sys", campaign_id=None, service="sourcing",
        event_name="discovery.run", phase=TracePhase.EMIT, timestamp=base,
    )

    repo = TraceRepository(mock_db)
    assert await repo.list_campaigns() == []


async def test_get_timeline_returns_events_ordered_ascending(mock_db):
    """The campaign timeline is ordered by timestamp ascending for human reading."""
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    # Insert out of order on purpose.
    await _insert(
        trace_id="t1", campaign_id="c-X", service="messaging",
        event_name="messaging.requested.consume", phase=TracePhase.START,
        timestamp=base.replace(second=30),
    )
    await _insert(
        trace_id="t1", campaign_id="c-X", service="gateway",
        event_name="campaign.created", phase=TracePhase.EMIT,
        timestamp=base.replace(second=0),
    )
    await _insert(
        trace_id="t1", campaign_id="c-X", service="planning",
        event_name="plan.ready.publish", phase=TracePhase.EMIT,
        timestamp=base.replace(second=15),
    )

    repo = TraceRepository(mock_db)
    timeline = await repo.get_timeline("c-X")

    assert [e.service for e in timeline] == ["gateway", "planning", "messaging"]


async def test_get_timeline_returns_empty_list_for_unknown_campaign(mock_db):
    """A campaign with no recorded events yields an empty timeline (not an error)."""
    repo = TraceRepository(mock_db)
    assert await repo.get_timeline("does-not-exist") == []
