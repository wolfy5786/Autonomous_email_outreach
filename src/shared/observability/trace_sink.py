"""Trace sink: pluggable destination for ``TraceEvent`` records.

The ``TracedBroker`` (and any other emitter) writes events to whatever sink is
currently active. In production each service calls
``set_trace_sink(MongoTraceSink())`` at startup after ``init_db()``; in tests use
``InMemoryTraceSink``. A ``None`` sink silently drops events — useful for
contexts where the database hasn't been initialised yet.

This module uses ``TYPE_CHECKING`` for ``TraceEvent`` so it stays importable by
services that don't have ``beanie`` installed. Services that actually use
``MongoTraceSink`` need beanie; others (e.g. a future prospecting service that
ships logs/metrics without Mongo) don't.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from shared.models import TraceEvent


class TraceSink(Protocol):
    """Destination for ``TraceEvent`` records. Implementations must be async-safe."""

    async def emit(self, event: TraceEvent) -> None:
        """Persist or otherwise handle a single trace event."""


class MongoTraceSink:
    """Writes ``TraceEvent`` rows to Mongo via Beanie. Requires ``init_db`` to have run."""

    async def emit(self, event: TraceEvent) -> None:
        await event.insert()


class InMemoryTraceSink:
    """Collects emitted events in a list. For tests and debugging only."""

    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    async def emit(self, event: TraceEvent) -> None:
        self.events.append(event)


_active_sink: TraceSink | None = None


def set_trace_sink(sink: TraceSink | None) -> None:
    """Set the global active trace sink. ``None`` disables trace event emission."""
    global _active_sink
    _active_sink = sink


def get_trace_sink() -> TraceSink | None:
    """Return the currently active trace sink, or ``None`` if none is set."""
    return _active_sink
