"""Tests for ``shared.observability.trace_context``."""

from __future__ import annotations

import pytest

from shared.observability.trace_context import (
    bind_trace_context,
    clear_trace_context,
    current_campaign_id,
    current_trace_id,
    trace_scope,
)


@pytest.fixture(autouse=True)
def _reset_trace_context():
    """Wipe trace context between tests so they don't leak through ContextVars."""
    yield
    clear_trace_context()


def test_bind_sets_current_ids():
    """Both ids should be readable after binding."""
    bind_trace_context(trace_id="t1", campaign_id="c1")
    assert current_trace_id() == "t1"
    assert current_campaign_id() == "c1"


def test_bind_skips_none_values():
    """Passing one id should leave the other untouched."""
    bind_trace_context(trace_id="t1")
    assert current_trace_id() == "t1"
    assert current_campaign_id() is None


def test_clear_removes_all_context():
    """clear_trace_context wipes both ids."""
    bind_trace_context(trace_id="t1", campaign_id="c1")
    clear_trace_context()
    assert current_trace_id() is None
    assert current_campaign_id() is None


def test_trace_scope_restores_prior_state():
    """trace_scope rebinds for its duration then restores the outer values."""
    bind_trace_context(trace_id="outer", campaign_id="outer-c")
    with trace_scope(trace_id="inner", campaign_id="inner-c"):
        assert current_trace_id() == "inner"
        assert current_campaign_id() == "inner-c"

    assert current_trace_id() == "outer"
    assert current_campaign_id() == "outer-c"


def test_trace_scope_clears_when_no_prior_state():
    """Exiting a trace_scope with no outer state should leave the context empty."""
    with trace_scope(trace_id="inner"):
        assert current_trace_id() == "inner"
    assert current_trace_id() is None
