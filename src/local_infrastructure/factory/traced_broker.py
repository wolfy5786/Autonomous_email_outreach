"""Decorator broker that adds trace propagation + event emission.

Wraps an inner :class:`MessageBroker` (RabbitMQ, future SQS, etc.) and adds the
cross-cutting observability concern without modifying the inner adapter.

* On ``publish``: stamps the current ``trace_id`` (from context) into the message
  if the caller hasn't set one, then emits a single ``EMIT`` event named
  ``"{topic}.publish"``.
* On ``subscribe``: extracts ``trace_id`` / ``campaign_id`` from each incoming
  message, binds them in a :func:`trace_scope`, emits ``START`` before the
  handler and ``END`` or ``ERROR`` after — both named ``"{topic}.consume"`` and
  carrying ``duration_ms``.

Sink writes are best-effort: a failing sink logs at WARNING but never breaks
the data plane — an observability outage must not cause message delivery to fail.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import structlog

from local_infrastructure.factory.broker_interface import MessageBroker, MessageHandler
from shared.observability.trace_context import (
    current_campaign_id,
    current_trace_id,
    trace_scope,
)
from shared.observability.trace_emit import make_event as _make_event
from shared.observability.trace_sink import get_trace_sink

log = structlog.get_logger()


class TracedBroker(MessageBroker):
    """Wraps a ``MessageBroker`` to inject trace context and emit ``TraceEvent`` rows."""

    def __init__(self, inner: MessageBroker, service: str) -> None:
        self._inner = inner
        self._service = service

    async def publish(self, topic: str, message: dict[str, Any]) -> None:
        trace_id = current_trace_id()
        # caller-supplied campaign_id wins; otherwise inherit from context.
        campaign_id = message.get("campaign_id") or current_campaign_id()

        if trace_id and "trace_id" not in message:
            message["trace_id"] = trace_id

        effective_trace_id = message.get("trace_id") or str(uuid.uuid4())

        await self._safe_emit(
            _make_event(
                trace_id=effective_trace_id,
                campaign_id=campaign_id,
                service=self._service,
                event_name=f"{topic}.publish",
                phase="emit",
                metadata={"topic": topic},
            )
        )
        await self._inner.publish(topic, message)

    async def subscribe(self, topic: str, handler: MessageHandler) -> None:
        service = self._service
        emit = self._safe_emit

        async def traced_handler(payload: dict[str, Any]) -> None:
            trace_id = payload.get("trace_id") or str(uuid.uuid4())
            campaign_id = payload.get("campaign_id")
            with trace_scope(trace_id=trace_id, campaign_id=campaign_id):
                await emit(
                    _make_event(
                        trace_id=trace_id,
                        campaign_id=campaign_id,
                        service=service,
                        event_name=f"{topic}.consume",
                        phase="start",
                        metadata={"topic": topic},
                    )
                )
                started = time.perf_counter()
                try:
                    await handler(payload)
                except Exception as exc:
                    duration_ms = int((time.perf_counter() - started) * 1000)
                    await emit(
                        _make_event(
                            trace_id=trace_id,
                            campaign_id=campaign_id,
                            service=service,
                            event_name=f"{topic}.consume",
                            phase="error",
                            duration_ms=duration_ms,
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                            metadata={"topic": topic},
                        )
                    )
                    raise

                duration_ms = int((time.perf_counter() - started) * 1000)
                await emit(
                    _make_event(
                        trace_id=trace_id,
                        campaign_id=campaign_id,
                        service=service,
                        event_name=f"{topic}.consume",
                        phase="end",
                        duration_ms=duration_ms,
                        metadata={"topic": topic},
                    )
                )

        await self._inner.subscribe(topic, traced_handler)

    async def disconnect(self) -> None:
        await self._inner.disconnect()

    async def ping(self) -> bool:
        return await self._inner.ping()

    async def _safe_emit(self, event: TraceEvent) -> None:
        """Emit to the active sink, swallowing sink failures with a WARN log."""
        sink = get_trace_sink()
        if sink is None:
            return
        try:
            await sink.emit(event)
        except Exception as exc:
            log.warning(
                "trace_sink_emit_failed",
                error_type=type(exc).__name__,
                error_message=str(exc),
                event_name=event.event_name,
            )
