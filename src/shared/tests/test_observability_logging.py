"""Tests for ``shared.observability.logging`` — JSON output carries standard fields."""

from __future__ import annotations

import json
import logging

import pytest
import structlog

from shared.observability.logging import configure_logging
from shared.observability.trace_context import bind_trace_context, clear_trace_context


@pytest.fixture(autouse=True)
def _reset_logging_state():
    """Reset structlog + stdlib logging between tests so configurations don't leak."""
    yield
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()
    clear_trace_context()
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)


def _last_json_line(stdout: str) -> dict:
    """Parse the most recent JSON line from a captured stdout block."""
    lines = [line for line in stdout.splitlines() if line.strip()]
    assert lines, f"expected at least one log line, got: {stdout!r}"
    return json.loads(lines[-1])


def test_log_line_includes_service_env_and_event(capsys):
    """Every emitted log line should be JSON tagged with service and env."""
    configure_logging(service="test-service", level="INFO", env="test-env")

    structlog.get_logger().info("hello", custom_field=42)

    payload = _last_json_line(capsys.readouterr().out)
    assert payload["service"] == "test-service"
    assert payload["env"] == "test-env"
    assert payload["event"] == "hello"
    assert payload["custom_field"] == 42
    assert payload["level"] == "info"
    assert "timestamp" in payload


def test_log_line_includes_bound_trace_context(capsys):
    """trace_id and campaign_id bound via bind_trace_context appear on every log line."""
    configure_logging(service="svc", level="INFO", env="test")

    bind_trace_context(trace_id="trace-abc", campaign_id="camp-123")
    structlog.get_logger().info("after_binding")

    payload = _last_json_line(capsys.readouterr().out)
    assert payload["trace_id"] == "trace-abc"
    assert payload["campaign_id"] == "camp-123"


def test_level_filtering_drops_lower_levels(capsys):
    """Logs below the configured level should not appear."""
    configure_logging(service="svc", level="WARNING", env="test")

    log = structlog.get_logger()
    log.info("invisible")
    log.warning("visible")

    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0])["event"] == "visible"
