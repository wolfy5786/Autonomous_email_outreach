"""Tests for AMQP helper functions (no live RabbitMQ)."""

from __future__ import annotations

import json

import pytest

from subscriber import _correlation_id_from_payload, _decode_body, _safe_broker_host


class _FakeLog:
    def __init__(self) -> None:
        self.warnings: list[tuple[str, BaseException | bool]] = []

    def warning(self, msg: str, *, exc_info: BaseException | bool = False) -> None:
        self.warnings.append((msg, exc_info))


def test_safe_broker_host_parses_url() -> None:
    assert "rabbitmq" in _safe_broker_host("amqp://guest:guest@rabbitmq:5672/")
    assert ":5672" in _safe_broker_host("amqp://guest:guest@rabbitmq:5672/")


def test_decode_body_accepts_object_json() -> None:
    fl = _FakeLog()
    raw = json.dumps({"campaign_id": "c", "plan_id": "p"}).encode()
    payload, err = _decode_body(raw, fl)
    assert err is None
    assert payload == {"campaign_id": "c", "plan_id": "p"}
    assert fl.warnings == []


def test_decode_body_rejects_invalid_json() -> None:
    fl = _FakeLog()
    payload, err = _decode_body(b"not-json", fl)
    assert payload is None
    assert err is not None
    assert fl.warnings


def test_correlation_id_from_request_id() -> None:
    cid = _correlation_id_from_payload({"request_id": "req-1", "campaign_id": "c"})
    assert cid == "req-1"


def test_correlation_id_generates_uuid_when_missing() -> None:
    cid = _correlation_id_from_payload({"campaign_id": "c"})
    assert len(cid) == 36
