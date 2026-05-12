"""Tests for ``shared.observability.trace_emit.trace_operation``."""

from __future__ import annotations

import pytest

from shared.models import TracePhase
from shared.observability.trace_context import (
    clear_trace_context,
    current_campaign_id,
    current_trace_id,
)
from shared.observability.trace_emit import trace_operation
from shared.observability.trace_sink import InMemoryTraceSink, set_trace_sink


@pytest.fixture
def sink() -> InMemoryTraceSink:
    s = InMemoryTraceSink()
    set_trace_sink(s)
    yield s
    set_trace_sink(None)
    clear_trace_context()


async def test_trace_operation_emits_start_then_end_on_success(sink: InMemoryTraceSink):
    """Success path: START then END for the same trace_id; END carries duration_ms."""
    async with trace_operation(
        trace_id="t-ok",
        campaign_id="c-ok",
        service="sourcing",
        event_name="sourcing.requested.consume",
    ):
        pass

    phases = [(e.phase, e.event_name, e.trace_id) for e in sink.events]
    assert phases == [
        (TracePhase.START, "sourcing.requested.consume", "t-ok"),
        (TracePhase.END, "sourcing.requested.consume", "t-ok"),
    ]
    assert sink.events[1].duration_ms is not None


async def test_trace_operation_emits_start_then_error_and_reraises(sink: InMemoryTraceSink):
    """Failure path: START then ERROR; the exception propagates."""

    class Boom(RuntimeError):
        pass

    with pytest.raises(Boom):
        async with trace_operation(
            trace_id="t-err",
            campaign_id="c-err",
            service="sourcing",
            event_name="op",
        ):
            raise Boom("boom")

    phases = [(e.phase, e.error_type) for e in sink.events]
    assert phases == [(TracePhase.START, None), (TracePhase.ERROR, "Boom")]
    assert sink.events[1].error_message == "boom"


async def test_trace_operation_binds_context_inside_block(sink: InMemoryTraceSink):
    """Inside the ``async with`` body, current_trace_id / current_campaign_id are bound."""
    seen: dict[str, str | None] = {}

    async with trace_operation(
        trace_id="t-bind",
        campaign_id="c-bind",
        service="svc",
        event_name="op",
    ):
        seen["trace_id"] = current_trace_id()
        seen["campaign_id"] = current_campaign_id()

    assert seen == {"trace_id": "t-bind", "campaign_id": "c-bind"}
    # After exit, scope is restored (no outer state in test → cleared).
    assert current_trace_id() is None


async def test_trace_operation_with_no_sink_still_runs(sink: InMemoryTraceSink):
    """If the sink is cleared mid-test, the block still completes normally."""
    set_trace_sink(None)

    async with trace_operation(
        trace_id="t-no-sink",
        campaign_id=None,
        service="svc",
        event_name="op",
    ):
        pass

    assert sink.events == []  # was active sink BEFORE we cleared, so nothing accumulated
