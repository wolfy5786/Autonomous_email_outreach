"""aio-pika client for ``plan.requested`` consume + events exchange publish — AMQP to the Docker broker only."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any, Protocol
from urllib.parse import urlparse

import aio_pika
import structlog
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustChannel, AbstractRobustConnection
from pydantic import ValidationError

from .config import Settings
from .handlers import NonRetryableError

log = structlog.get_logger(__name__)

HandlerFn = Callable[[dict[str, Any]], Awaitable[None]]
MessageCallback = Callable[[AbstractIncomingMessage], Awaitable[None]]


def _safe_broker_host(amqp_url: str) -> str:
    parsed = urlparse(amqp_url)
    host = parsed.hostname or "unknown"
    if parsed.port:
        return f"{host}:{parsed.port}"
    return host


def _correlation_fields(message: AbstractIncomingMessage) -> dict[str, Any]:
    fields: dict[str, Any] = {"delivery_tag": message.delivery_tag}
    if message.message_id:
        fields["message_id"] = message.message_id
    if message.correlation_id:
        fields["correlation_id"] = message.correlation_id
    return fields


class _LogWarn(Protocol):
    def warning(self, msg: str, *, exc_info: BaseException | bool = False) -> None: ...


def _decode_body(body: bytes, logger: _LogWarn) -> tuple[dict[str, Any] | None, Exception | None]:
    try:
        text = body.decode("utf-8")
        data = json.loads(text)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("plan.requested message decode failed, sending to DLQ", exc_info=exc)
        return None, exc

    if not isinstance(data, dict):
        exc = TypeError(f"JSON root must be object, got {type(data).__name__}")
        logger.warning("plan.requested message invalid shape, sending to DLQ", exc_info=exc)
        return None, exc

    return data, None


class PlanningAMQPClient:
    """AMQP client: passive ``plan.requested`` consumer + publish to the pipeline events exchange."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractRobustChannel | None = None
        self._consumer_tag: str | None = None

    async def connect(self) -> None:
        log.info(
            "rabbitmq connecting",
            module=__name__,
            queue=self._settings.plan_requested_queue,
            broker_host=_safe_broker_host(self._settings.rabbitmq_url),
            exchange=self._settings.rabbitmq_exchange,
        )
        self._connection = await aio_pika.connect_robust(self._settings.rabbitmq_url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=self._settings.rabbit_prefetch)
        log.info(
            "rabbitmq connected",
            module=__name__,
            broker_host=_safe_broker_host(self._settings.rabbitmq_url),
        )

    async def start_consumer(self, handler: HandlerFn) -> None:
        if self._channel is None:
            raise RuntimeError("RabbitMQ channel is not open; call connect() first")

        queue = await self._channel.declare_queue(
            self._settings.plan_requested_queue,
            passive=True,
        )
        self._consumer_tag = await queue.consume(
            self._make_callback(handler),
            no_ack=False,
        )
        log.info(
            "rabbitmq consumer registered",
            module=__name__,
            queue=self._settings.plan_requested_queue,
            consumer_tag=self._consumer_tag,
        )

    def _make_callback(self, handler: HandlerFn) -> MessageCallback:
        async def _callback(message: AbstractIncomingMessage) -> None:
            await _handle_incoming(message, handler, self._settings.plan_requested_queue)

        return _callback

    async def publish(self, routing_key: str, message: dict[str, Any]) -> None:
        if self._channel is None:
            log.error("rabbitmq publish skipped — channel not open", module=__name__, routing_key=routing_key)
            raise RuntimeError("RabbitMQ channel is not open")

        body = json.dumps(message).encode("utf-8")
        try:
            exchange = await self._channel.get_exchange(self._settings.rabbitmq_exchange, ensure=True)
            await exchange.publish(
                aio_pika.Message(body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
                routing_key=routing_key,
            )
            log.info("rabbitmq message published", module=__name__, routing_key=routing_key)
        except Exception as exc:
            log.error(
                "rabbitmq publish failed",
                module=__name__,
                routing_key=routing_key,
                exc_info=True,
            )
            raise RuntimeError(f"publish failed for routing_key={routing_key}") from exc

    async def disconnect(self) -> None:
        if self._channel is not None and self._consumer_tag:
            try:
                await self._channel.cancel(self._consumer_tag)
            except Exception:
                log.error("rabbitmq consumer cancel failed", module=__name__, exc_info=True)
            self._consumer_tag = None

        if self._connection is not None:
            try:
                await self._connection.close()
            except Exception:
                log.error("rabbitmq connection close failed", module=__name__, exc_info=True)

        self._connection = None
        self._channel = None


async def _handle_incoming(
    message: AbstractIncomingMessage,
    handler: HandlerFn,
    queue_name: str,
) -> None:
    base_ctx = _correlation_fields(message)
    logger = log.bind(module=__name__, queue=queue_name, **base_ctx)

    payload, decode_exc = _decode_body(message.body, logger)
    if decode_exc is not None:
        await message.reject(requeue=False)
        return

    cid = payload.get("campaign_id")
    logger = logger.bind(campaign_id=cid) if cid is not None else logger
    logger.info("plan.requested delivery received")

    try:
        await handler(payload)
    except NonRetryableError as exc:
        logger.error("plan.requested handler non-retryable failure", exc_info=exc)
        await message.reject(requeue=False)
        return
    except ValidationError as exc:
        logger.error("plan.requested validation failed, sending to DLQ", exc_info=exc)
        await message.reject(requeue=False)
        return
    except Exception as exc:
        logger.error("plan.requested handler transient failure, nack requeue", exc_info=exc)
        await message.nack(requeue=True)
        return

    logger.info("plan.requested processed, ack")
    await message.ack()
