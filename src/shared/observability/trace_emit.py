"""Helpers for emitting ``TraceEvent`` records outside the broker decorator.

The :func:`trace_operation` async context manager lets services that don't route
through :class:`TracedBroker` (e.g. sourcing's custom broker, gateway HTTP request
handlers, scheduled jobs) instrument arbitrary operations with the same
START / END / ERROR lifecycle the broker produces.

``shared.models`` is imported lazily inside :func:`make_event` so this module
stays importable in services that don't have ``beanie`` installed.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncIterator

from shared.observability.trace_context import trace_scope
from shared.observability.trace_sink import get_trace_sink

if TYPE_CHECKING:
    from shared.models import TraceEvent


def make_event(
    *,
    trace_id: str,
    campaign_id: str | None,
    service: str,
    event_name: str,
    phase: str,
    duration_ms: int | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> TraceEvent:
    """Construct a :class:`TraceEvent`. Lazy-imports ``shared.models``."""
    from shared.models import TraceEvent, TracePhase

    return TraceEvent(
        trace_id=trace_id,
        campaign_id=campaign_id,
        service=service,
        event_name=event_name,
        phase=TracePhase(phase),
        duration_ms=duration_ms,
        error_type=error_type,
        error_message=error_message,
        metadata=metadata or {},
    )


async def _emit_safely(event: TraceEvent) -> None:
    """Forward an event to the active sink; never raise. Mirrors the broker policy:
    a failing sink must not break the data plane."""
    sink = get_trace_sink()
    if sink is None:
        return
    try:
        await sink.emit(event)
    except Exception:  # noqa: BLE001 — best-effort, swallow + log via structlog if needed
        import structlog

        structlog.get_logger().warning(
            "trace_sink_emit_failed",
            event_name=event.event_name,
        )


@asynccontextmanager
async def trace_operation(
    *,
    trace_id: str,
    campaign_id: str | None,
    service: str,
    event_name: str,
    metadata: dict[str, Any] | None = None,
) -> AsyncIterator[None]:
    """Bind trace context for the block, emit ``START`` before and ``END`` / ``ERROR`` after.

    Use this when wrapping a non-broker operation (e.g. an HTTP request handler,
    a manual broker consume loop). The trace context propagates to any logger and
    to any subsequent ``broker.publish`` call inside the block.

    Args:
        trace_id: Identifier shared across services for this whole operation chain.
        campaign_id: Optional business identifier — included on the event timeline.
        service: Name of the service emitting the event.
        event_name: Stable name for the operation (e.g. ``"sourcing.requested.consume"``).
        metadata: Optional free-form context (queue name, retry_count, etc.).
    """
    with trace_scope(trace_id=trace_id, campaign_id=campaign_id):
        await _emit_safely(
            make_event(
                trace_id=trace_id,
                campaign_id=campaign_id,
                service=service,
                event_name=event_name,
                phase="start",
                metadata=metadata,
            )
        )
        started = time.perf_counter()
        try:
            yield
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            await _emit_safely(
                make_event(
                    trace_id=trace_id,
                    campaign_id=campaign_id,
                    service=service,
                    event_name=event_name,
                    phase="error",
                    duration_ms=duration_ms,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    metadata=metadata,
                )
            )
            raise

        duration_ms = int((time.perf_counter() - started) * 1000)
        await _emit_safely(
            make_event(
                trace_id=trace_id,
                campaign_id=campaign_id,
                service=service,
                event_name=event_name,
                phase="end",
                duration_ms=duration_ms,
                metadata=metadata,
            )
        )
