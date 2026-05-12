"""aio-pika publisher for sourcing stage handoff — emits to the shared topic exchange."""

from __future__ import annotations

import json
from typing import Any

import aio_pika
import structlog
from aio_pika.abc import AbstractRobustChannel, AbstractRobustConnection, AbstractRobustExchange

from config import Settings

log = structlog.get_logger(__name__)


class SourcingAMQPPublisher:
    """Publishes ``sourcing.completed`` and downstream ``prospecting.requested`` events."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractRobustChannel | None = None
        self._exchange: AbstractRobustExchange | None = None

    async def _publish_json(self, routing_key: str, payload: dict[str, Any]) -> None:
        if self._exchange is None:
            raise RuntimeError("Publisher exchange is not initialized; call connect() first")

        body = json.dumps(payload, default=str).encode("utf-8")
        message = aio_pika.Message(
            body=body,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            correlation_id=payload.get("request_id"),
        )
        await self._exchange.publish(message, routing_key=routing_key)

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(self._settings.rabbitmq_url)
        self._channel = await self._connection.channel(publisher_confirms=True)
        self._exchange = await self._channel.declare_exchange(
            self._settings.events_exchange,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
            passive=True,
        )
        log.info(
            "rabbitmq publisher connected",
            module=__name__,
            exchange=self._settings.events_exchange,
        )

    async def publish_completed(self, payload: dict[str, Any]) -> None:
        routing_key = self._settings.sourcing_completed_routing_key
        await self._publish_json(routing_key, payload)
        log.info(
            "sourcing.completed published",
            module=__name__,
            routing_key=routing_key,
            campaign_id=payload.get("campaign_id"),
            plan_id=payload.get("plan_id"),
            request_id=payload.get("request_id"),
            entity_count=len(payload.get("entity_ids") or []),
        )

    async def publish_prospecting_requested(self, payload: dict[str, Any]) -> None:
        routing_key = self._settings.prospecting_requested_routing_key
        await self._publish_json(routing_key, payload)
        log.info(
            "prospecting.requested published",
            module=__name__,
            routing_key=routing_key,
            campaign_id=payload.get("campaign_id"),
            plan_id=payload.get("plan_id"),
            entity_count=len(payload.get("entity_ids") or []),
        )

    async def disconnect(self) -> None:
        if self._channel is not None:
            try:
                await self._channel.close()
            except Exception:
                log.error("rabbitmq publisher channel close failed", module=__name__, exc_info=True)
        if self._connection is not None:
            try:
                await self._connection.close()
            except Exception:
                log.error("rabbitmq publisher connection close failed", module=__name__, exc_info=True)
        self._channel = None
        self._exchange = None
        self._connection = None
