"""Tests for ``local_infrastructure.factory.traced_broker.TracedBroker``.

Verifies trace propagation and ``TraceEvent`` emission for publish + consume,
using an :class:`InMemoryTraceSink` and a fake inner broker.
"""

from __future__ import annotations

from typing import Any

import pytest

from local_infrastructure.factory.broker_interface import MessageBroker, MessageHandler
from local_infrastructure.factory.traced_broker import TracedBroker
from shared.models import TracePhase
from shared.observability.trace_context import (
    bind_trace_context,
    clear_trace_context,
    current_trace_id,
)
from shared.observability.trace_sink import InMemoryTraceSink, set_trace_sink


class FakeBroker(MessageBroker):
    """Records published messages and exposes a way to inject incoming ones."""

    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []
        self._handlers: dict[str, MessageHandler] = {}

    async def publish(self, topic: str, message: dict[str, Any]) -> None:
        self.published.append((topic, message))

    async def subscribe(self, topic: str, handler: MessageHandler) -> None:
        self._handlers[topic] = handler

    async def disconnect(self) -> None:
        return None

    async def deliver(self, topic: str, payload: dict[str, Any]) -> None:
        """Test helper: invoke the registered handler for ``topic`` with ``payload``."""
        await self._handlers[topic](payload)

    async def ping(self) -> bool:
        return self.ping_result

    ping_result: bool = True


@pytest.fixture
def sink() -> InMemoryTraceSink:
    s = InMemoryTraceSink()
    set_trace_sink(s)
    yield s
    set_trace_sink(None)
    clear_trace_context()


@pytest.fixture
def inner() -> FakeBroker:
    return FakeBroker()


@pytest.fixture
def traced(inner: FakeBroker) -> TracedBroker:
    return TracedBroker(inner, service="test-service")


async def test_publish_emits_one_event_and_forwards_to_inner(
    traced: TracedBroker, inner: FakeBroker, sink: InMemoryTraceSink
):
    """Publishing forwards to the inner broker and emits exactly one EMIT trace event."""
    await traced.publish("topic.a", {"trace_id": "t1", "campaign_id": "c1", "foo": "bar"})

    assert inner.published == [("topic.a", {"trace_id": "t1", "campaign_id": "c1", "foo": "bar"})]
    assert len(sink.events) == 1
    event = sink.events[0]
    assert event.phase is TracePhase.EMIT
    assert event.event_name == "topic.a.publish"
    assert event.trace_id == "t1"
    assert event.campaign_id == "c1"
    assert event.service == "test-service"
    assert event.metadata == {"topic": "topic.a"}


async def test_publish_injects_trace_id_from_context(
    traced: TracedBroker, inner: FakeBroker, sink: InMemoryTraceSink
):
    """If the message has no trace_id, the current context's trace_id is stamped in."""
    bind_trace_context(trace_id="from-context", campaign_id="c-ctx")
    await traced.publish("topic.b", {"foo": "bar"})

    sent_topic, sent_msg = inner.published[0]
    assert sent_topic == "topic.b"
    assert sent_msg["trace_id"] == "from-context"
    # campaign_id is for the trace event, not auto-stamped on the message
    assert sink.events[0].trace_id == "from-context"
    assert sink.events[0].campaign_id == "c-ctx"


async def test_publish_does_not_overwrite_caller_trace_id(
    traced: TracedBroker, inner: FakeBroker, sink: InMemoryTraceSink
):
    """Caller-supplied trace_id wins over context."""
    bind_trace_context(trace_id="from-context")
    await traced.publish("topic.c", {"trace_id": "from-caller"})

    assert inner.published[0][1]["trace_id"] == "from-caller"
    assert sink.events[0].trace_id == "from-caller"


async def test_publish_generates_trace_id_when_none_present(
    traced: TracedBroker, inner: FakeBroker, sink: InMemoryTraceSink
):
    """With no trace_id in payload or context, a fresh UUID is generated for the event."""
    await traced.publish("topic.d", {"foo": "bar"})

    event = sink.events[0]
    assert event.trace_id  # non-empty
    # No trace_id was stamped on the outgoing message because nothing was in context.
    assert "trace_id" not in inner.published[0][1]


async def test_consume_binds_trace_context_for_handler(
    traced: TracedBroker, inner: FakeBroker, sink: InMemoryTraceSink
):
    """Handler sees trace_id bound in context, taken from the incoming message."""
    seen: dict[str, str | None] = {}

    async def handler(payload: dict[str, Any]) -> None:
        seen["trace_id"] = current_trace_id()

    await traced.subscribe("topic.e", handler)
    await inner.deliver("topic.e", {"trace_id": "msg-trace", "campaign_id": "msg-camp"})

    assert seen["trace_id"] == "msg-trace"


async def test_consume_emits_start_then_end_on_success(
    traced: TracedBroker, inner: FakeBroker, sink: InMemoryTraceSink
):
    """A successful consume produces START then END for the same trace_id."""

    async def handler(_: dict[str, Any]) -> None:
        return None

    await traced.subscribe("topic.f", handler)
    await inner.deliver("topic.f", {"trace_id": "t-ok", "campaign_id": "c-ok"})

    phases = [(e.phase, e.event_name, e.trace_id) for e in sink.events]
    assert phases == [
        (TracePhase.START, "topic.f.consume", "t-ok"),
        (TracePhase.END, "topic.f.consume", "t-ok"),
    ]
    assert sink.events[1].duration_ms is not None
    assert sink.events[1].duration_ms >= 0


async def test_consume_emits_start_then_error_and_reraises(
    traced: TracedBroker, inner: FakeBroker, sink: InMemoryTraceSink
):
    """A handler exception produces START then ERROR; the exception is re-raised."""

    class BoomError(RuntimeError):
        pass

    async def handler(_: dict[str, Any]) -> None:
        raise BoomError("kaboom")

    await traced.subscribe("topic.g", handler)
    with pytest.raises(BoomError):
        await inner.deliver("topic.g", {"trace_id": "t-err"})

    phases = [(e.phase, e.event_name) for e in sink.events]
    assert phases == [
        (TracePhase.START, "topic.g.consume"),
        (TracePhase.ERROR, "topic.g.consume"),
    ]
    err_event = sink.events[1]
    assert err_event.error_type == "BoomError"
    assert err_event.error_message == "kaboom"
    assert err_event.duration_ms is not None


async def test_publish_still_works_when_no_sink_configured(
    traced: TracedBroker, inner: FakeBroker
):
    """With no sink, publish proceeds without emitting events and without error."""
    set_trace_sink(None)
    await traced.publish("topic.h", {"foo": "bar"})
    assert inner.published == [("topic.h", {"foo": "bar"})]


async def test_ping_delegates_to_inner_broker(
    traced: TracedBroker, inner: FakeBroker
):
    """TracedBroker.ping forwards to the wrapped broker's ping."""
    inner.ping_result = True
    assert await traced.ping() is True
    inner.ping_result = False
    assert await traced.ping() is False


async def test_consume_still_works_when_sink_fails(
    traced: TracedBroker, inner: FakeBroker
):
    """A failing sink must not break message processing."""

    class ExplodingSink:
        async def emit(self, _event):
            raise RuntimeError("sink offline")

    set_trace_sink(ExplodingSink())

    delivered: list[dict[str, Any]] = []

    async def handler(payload: dict[str, Any]) -> None:
        delivered.append(payload)

    await traced.subscribe("topic.i", handler)
    await inner.deliver("topic.i", {"trace_id": "t-i"})

    assert delivered == [{"trace_id": "t-i"}]

    set_trace_sink(None)
