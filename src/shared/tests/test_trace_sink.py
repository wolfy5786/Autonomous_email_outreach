"""Tests for ``shared.observability.trace_sink``."""

from __future__ import annotations

import pytest

from shared.models import TraceEvent, TracePhase
from shared.observability.trace_sink import (
    InMemoryTraceSink,
    get_trace_sink,
    set_trace_sink,
)


@pytest.fixture(autouse=True)
def _reset_global_sink():
    yield
    set_trace_sink(None)


async def test_in_memory_sink_stores_events():
    """InMemoryTraceSink.emit appends to its list."""
    sink = InMemoryTraceSink()
    event = TraceEvent(
        trace_id="t1",
        service="svc",
        event_name="x.publish",
        phase=TracePhase.EMIT,
    )
    await sink.emit(event)
    assert sink.events == [event]


def test_set_and_get_trace_sink_round_trip():
    """set_trace_sink stores; get_trace_sink reads back the same instance."""
    sink = InMemoryTraceSink()
    set_trace_sink(sink)
    assert get_trace_sink() is sink


def test_set_trace_sink_none_disables_emission():
    """Setting to None clears the active sink."""
    set_trace_sink(InMemoryTraceSink())
    set_trace_sink(None)
    assert get_trace_sink() is None
