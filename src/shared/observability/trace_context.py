"""Trace context: per-task ``trace_id`` and ``campaign_id`` carried via ``ContextVar``.

These context vars are read by the structlog processor configured in
``shared.observability.logging`` and stamped onto every log line, so logging
"just works" once a service has called :func:`bind_trace_context` on entry.

Using plain :mod:`contextvars` (rather than ``structlog.contextvars``) keeps this
module independent of structlog's internal API surface — any process that imports
the trace ids back out can do so without depending on structlog.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
_campaign_id: ContextVar[str | None] = ContextVar("campaign_id", default=None)


def bind_trace_context(
    *,
    trace_id: str | None = None,
    campaign_id: str | None = None,
) -> None:
    """Bind trace identifiers to the current async/thread context.

    Only non-``None`` values are bound; pass one or both. Subsequent ``structlog``
    calls in this context will carry these identifiers automatically.
    """
    if trace_id is not None:
        _trace_id.set(trace_id)
    if campaign_id is not None:
        _campaign_id.set(campaign_id)


def clear_trace_context() -> None:
    """Clear bound trace identifiers in the current context."""
    _trace_id.set(None)
    _campaign_id.set(None)


def current_trace_id() -> str | None:
    """Return the ``trace_id`` bound in the current context, or ``None``."""
    return _trace_id.get()


def current_campaign_id() -> str | None:
    """Return the ``campaign_id`` bound in the current context, or ``None``."""
    return _campaign_id.get()


@contextmanager
def trace_scope(
    *,
    trace_id: str | None = None,
    campaign_id: str | None = None,
) -> Iterator[None]:
    """Bind trace identifiers for a ``with`` block and restore prior state on exit.

    Use on consumer entry points so each incoming message has its own scope and a
    later message can't inherit a stale ``trace_id`` from the previous one.
    """
    trace_token = _trace_id.set(trace_id) if trace_id is not None else None
    campaign_token = _campaign_id.set(campaign_id) if campaign_id is not None else None
    try:
        yield
    finally:
        if campaign_token is not None:
            _campaign_id.reset(campaign_token)
        if trace_token is not None:
            _trace_id.reset(trace_token)
