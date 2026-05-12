"""Shared structlog setup for all email_outreach services.

Replaces the per-service ``logging_setup.py`` duplicates. Emits JSON to stdout and
stamps every log line with:

* ``service`` and ``env`` (from arguments or env vars)
* ``trace_id`` / ``campaign_id`` (from :mod:`shared.observability.trace_context`,
  via the :func:`_merge_trace_context` processor)
* anything bound via ``structlog.contextvars`` (kept for backwards compatibility)
"""

from __future__ import annotations

import logging
import os
from typing import Any, MutableMapping

import structlog

from shared.observability.trace_context import current_campaign_id, current_trace_id


def configure_logging(
    service: str,
    level: str | None = None,
    env: str | None = None,
) -> None:
    """Configure structlog + stdlib logging for JSON output to stdout.

    Args:
        service: Service name (e.g. ``"planning"``). Stamped on every log line.
        level: Log level; defaults to the ``LOG_LEVEL`` env var or ``"INFO"``.
        env: Deployment environment (e.g. ``"local"``, ``"prod"``); defaults to
            the ``ENV`` env var or ``"local"``. Stamped on every log line.
    """
    resolved_level = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    resolved_env = env or os.getenv("ENV") or "local"

    logging.basicConfig(format="%(message)s", level=resolved_level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _merge_trace_context,
            _stamp_service_and_env(service, resolved_env),
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[resolved_level]
        ),
        cache_logger_on_first_use=True,
    )


def _merge_trace_context(
    _logger: Any,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Stamp ``trace_id`` / ``campaign_id`` from the current context onto the event."""
    trace_id = current_trace_id()
    campaign_id = current_campaign_id()
    if trace_id is not None:
        event_dict.setdefault("trace_id", trace_id)
    if campaign_id is not None:
        event_dict.setdefault("campaign_id", campaign_id)
    return event_dict


def _stamp_service_and_env(service: str, env: str):
    """Return a processor that stamps the configured ``service`` and ``env`` fields."""

    def processor(
        _logger: Any,
        _method_name: str,
        event_dict: MutableMapping[str, Any],
    ) -> MutableMapping[str, Any]:
        event_dict.setdefault("service", service)
        event_dict.setdefault("env", env)
        return event_dict

    return processor
