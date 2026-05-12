"""aio-pika consumer for ``sourcing.requested`` — no factory; app speaks AMQP to the Docker broker."""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Protocol
from urllib.parse import urlparse

import aio_pika
import structlog
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection

from config import Settings
from handlers import NonRetryableSourcingError, execute_sourcing_pipeline
from pipeline import SourcingPipeline

log = structlog.get_logger(__name__)

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
        logger.warning("sourcing message decode failed, sending to DLQ", exc_info=exc)
        return None, exc

    if not isinstance(data, dict):
        exc = TypeError(f"JSON root must be object, got {type(data).__name__}")
        logger.warning("sourcing message invalid shape, sending to DLQ", exc_info=exc)
        return None, exc

    return data, None


def _correlation_id_from_payload(payload: dict[str, Any]) -> str:
    rid = payload.get("request_id")
    if isinstance(rid, str) and rid.strip():
        return rid.strip()
    return str(uuid.uuid4())


class SourcingAMQPConsumer:
    """Minimal AMQP consumer: one queue, manual acks, DLQ via reject(requeue=False)."""

    def __init__(self, settings: Settings, pipeline: SourcingPipeline) -> None:
        self._settings = settings
        self._pipeline = pipeline
        self._connection: AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractRobustChannel | None = None
        self._consumer_tag: str | None = None

    async def connect(self) -> None:
        log.info(
            "rabbitmq connecting",
            module=__name__,
            queue=self._settings.sourcing_requested_queue,
            broker_host=_safe_broker_host(self._settings.rabbitmq_url),
        )
        self._connection = await aio_pika.connect_robust(self._settings.rabbitmq_url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=self._settings.rabbit_prefetch)
        log.info(
            "rabbitmq connected",
            module=__name__,
            broker_host=_safe_broker_host(self._settings.rabbitmq_url),
        )

    async def start_consumer(self) -> None:
        if self._channel is None:
            raise RuntimeError("RabbitMQ channel is not open; call connect() first")

        queue = await self._channel.declare_queue(
            self._settings.sourcing_requested_queue,
            passive=True,
        )
        self._consumer_tag = await queue.consume(
            self._make_callback(),
            no_ack=False,
        )
        log.info(
            "rabbitmq consumer registered",
            module=__name__,
            queue=self._settings.sourcing_requested_queue,
            consumer_tag=self._consumer_tag,
        )

    def _make_callback(self) -> MessageCallback:
        async def _callback(message: AbstractIncomingMessage) -> None:
            await self._handle_incoming(message)

        return _callback

    async def _handle_incoming(self, message: AbstractIncomingMessage) -> None:
        base_ctx = _correlation_fields(message)
        logger = log.bind(module=__name__, queue=self._settings.sourcing_requested_queue, **base_ctx)

        payload, decode_exc = _decode_body(message.body, logger)
        if decode_exc is not None:
            await message.reject(requeue=False)
            return

        cid = _correlation_id_from_payload(payload)
        logger = logger.bind(correlation_id=cid)

        campaign_id = payload.get("campaign_id")
        if campaign_id is not None:
            logger = logger.bind(campaign_id=campaign_id)

        logger.info("sourcing.requested delivery received")

        try:
            await execute_sourcing_pipeline(message.body, self._pipeline)
        except NonRetryableSourcingError as exc:
            logger.error("sourcing job non-retryable failure", exc_info=exc)
            await message.reject(requeue=False)
            return
        except Exception as exc:
            logger.error("sourcing job transient failure, nack requeue", exc_info=exc)
            await message.nack(requeue=True)
            return

        logger.info("sourcing.requested processed, ack")
        await message.ack()

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
