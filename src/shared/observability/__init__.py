"""Shared observability utilities for the email_outreach services.

Public surfaces:

* :func:`configure_logging` — set up structured JSON logging once at startup.
* trace context helpers — bind ``trace_id`` / ``campaign_id`` to the current
  task so every subsequent log line (and every trace event emitted by the
  broker middleware) carries those identifiers automatically.
* trace sink — pluggable destination for :class:`TraceEvent` records.
"""

from shared.observability.logging import configure_logging
from shared.observability.trace_context import (
    bind_trace_context,
    clear_trace_context,
    current_campaign_id,
    current_trace_id,
    trace_scope,
)
from shared.observability.trace_emit import make_event, trace_operation
from shared.observability.trace_sink import (
    InMemoryTraceSink,
    MongoTraceSink,
    TraceSink,
    get_trace_sink,
    set_trace_sink,
)

__all__ = (
    "InMemoryTraceSink",
    "MongoTraceSink",
    "TraceSink",
    "bind_trace_context",
    "clear_trace_context",
    "configure_logging",
    "current_campaign_id",
    "current_trace_id",
    "get_trace_sink",
    "make_event",
    "set_trace_sink",
    "trace_operation",
    "trace_scope",
)
