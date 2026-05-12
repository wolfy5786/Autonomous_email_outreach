"""Unit tests for planning AMQP subscriber helpers (no real broker)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from planning.config import Settings
from planning.handlers import NonRetryableError
from planning.schemas import PlanRequestedEvent
from planning.subscriber import (
    PlanningAMQPClient,
    _decode_body,
    _handle_incoming,
)


def _incoming_message(body: bytes) -> MagicMock:
    msg = MagicMock()
    msg.body = body
    msg.delivery_tag = 7
    msg.message_id = "mid-1"
    msg.correlation_id = "corr-1"
    msg.ack = AsyncMock()
    msg.reject = AsyncMock()
    msg.nack = AsyncMock()
    return msg


@pytest.mark.asyncio
async def test_handle_incoming_acks_when_handler_succeeds() -> None:
    handler = AsyncMock()
    msg = _incoming_message(b'{"campaign_id": "c1"}')

    await _handle_incoming(msg, handler, "plan.requested")

    handler.assert_awaited_once_with({"campaign_id": "c1"})
    msg.ack.assert_awaited_once()
    msg.reject.assert_not_awaited()
    msg.nack.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_incoming_rejects_invalid_json_without_requeue() -> None:
    handler = AsyncMock()
    msg = _incoming_message(b"not json{")

    await _handle_incoming(msg, handler, "plan.requested")

    handler.assert_not_awaited()
    msg.reject.assert_awaited_once_with(requeue=False)
    msg.ack.assert_not_awaited()
    msg.nack.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_incoming_rejects_when_json_root_is_not_object() -> None:
    handler = AsyncMock()
    msg = _incoming_message(b"[1,2,3]")

    await _handle_incoming(msg, handler, "plan.requested")

    handler.assert_not_awaited()
    msg.reject.assert_awaited_once_with(requeue=False)


@pytest.mark.asyncio
async def test_handle_incoming_rejects_on_non_retryable_error() -> None:
    async def fail(_: dict[str, object]) -> None:
        raise NonRetryableError("campaign missing")

    msg = _incoming_message(b'{"campaign_id": "c1"}')
    await _handle_incoming(msg, fail, "plan.requested")

    msg.reject.assert_awaited_once_with(requeue=False)
    msg.ack.assert_not_awaited()
    msg.nack.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_incoming_rejects_on_validation_error() -> None:
    async def invalid(_: dict[str, object]) -> None:
        PlanRequestedEvent.model_validate({"not_campaign_id": "x"})

    msg = _incoming_message(b'{"campaign_id": "c1"}')
    await _handle_incoming(msg, invalid, "plan.requested")

    msg.reject.assert_awaited_once_with(requeue=False)
    msg.nack.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_incoming_nacks_with_requeue_on_transient_error() -> None:
    async def boom(_: dict[str, object]) -> None:
        raise ConnectionError("upstream down")

    msg = _incoming_message(b'{"campaign_id": "c1"}')
    await _handle_incoming(msg, boom, "plan.requested")

    msg.nack.assert_awaited_once_with(requeue=True)
    msg.reject.assert_not_awaited()
    msg.ack.assert_not_awaited()


@pytest.mark.asyncio
async def test_publish_raises_when_channel_not_open() -> None:
    client = PlanningAMQPClient(Settings())
    with pytest.raises(RuntimeError, match="channel is not open"):
        await client.publish("plan.ready", {"campaign_id": "c"})


def test_decode_body_returns_dict() -> None:
    log = MagicMock()
    data, err = _decode_body(b'{"a": 1}', log)
    assert err is None
    assert data == {"a": 1}


def test_decode_body_returns_error_for_malformed_json() -> None:
    log = MagicMock()
    data, err = _decode_body(b"x", log)
    assert data is None
    assert err is not None


@pytest.mark.asyncio
async def test_connect_and_start_consumer_registers_consumer() -> None:
    settings = Settings(
        rabbitmq_url="amqp://guest:guest@localhost:5672/",
        plan_requested_queue="plan.requested",
        rabbit_prefetch=3,
    )
    client = PlanningAMQPClient(settings)

    channel = MagicMock()
    channel.set_qos = AsyncMock()
    channel.cancel = AsyncMock()
    channel.declare_queue = AsyncMock()
    channel.get_exchange = AsyncMock()

    queue = MagicMock()
    queue.consume = AsyncMock(return_value="consumer-tag-1")
    channel.declare_queue.return_value = queue

    connection = MagicMock()
    connection.channel = AsyncMock(return_value=channel)
    connection.close = AsyncMock()

    with patch("planning.subscriber.aio_pika.connect_robust", AsyncMock(return_value=connection)):
        await client.connect()

    handler = AsyncMock()
    await client.start_consumer(handler)

    queue.consume.assert_awaited_once()
    assert client._consumer_tag == "consumer-tag-1"
    kwargs = queue.consume.call_args.kwargs
    assert kwargs.get("no_ack") is False

    await client.disconnect()
    channel.cancel.assert_awaited_once_with("consumer-tag-1")
    connection.close.assert_awaited()
