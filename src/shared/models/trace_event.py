"""Trace event document: append-only record of observability events emitted across services.

Each operation that we want to follow on the campaign timeline produces one or more
``TraceEvent`` rows — typically a ``START`` when work begins and an ``END`` (or ``ERROR``)
when it finishes, or a single ``EMIT`` for one-shot events like ``campaign.created``.

The observability UI (later step) reads from the ``trace_events`` collection, grouped by
``campaign_id``, ordered by ``timestamp``, to render a per-campaign timeline.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel

from shared.models.enums import TracePhase


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TraceEvent(Document):
    """Persisted trace event (collection ``trace_events``)."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str
    campaign_id: str | None = None
    service: str
    event_name: str
    phase: TracePhase
    timestamp: datetime = Field(default_factory=_utcnow)
    duration_ms: int | None = None
    error_type: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Settings:
        name = "trace_events"
        indexes = [
            IndexModel(
                [("campaign_id", ASCENDING), ("timestamp", ASCENDING)],
                name="campaign_timeline",
            ),
            IndexModel(
                [("trace_id", ASCENDING), ("timestamp", ASCENDING)],
                name="trace_timeline",
            ),
            IndexModel(
                [("service", ASCENDING), ("event_name", ASCENDING), ("timestamp", ASCENDING)],
                name="service_event_timeline",
            ),
        ]
