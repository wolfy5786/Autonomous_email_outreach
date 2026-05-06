import asyncio
import json
import logging
import os
from typing import Any

import aio_pika
from aio_pika.abc import (
    AbstractExchange,
    AbstractRobustChannel,
    AbstractRobustConnection,
    AbstractRobustQueue,
)

from local_infrastructure.factory.broker_interface import MessageBroker, MessageHandler, NonRetryableError

log = logging.getLogger(__name__)


class RabbitMQBroker(MessageBroker):
    """aio-pika adapter.

    Topology is provisioned out-of-band via `rabbit_mq/definitions.json`:
      - topic exchange `email_outreach.events` for pipeline events
      - dead-letter exchange `email_outreach.dlx` for rejected messages
      - one durable queue per event, each with a sibling `<topic>.dlq` queue
        bound to the DLX with routing key `<topic>.dlq`

    The adapter therefore does NOT declare queues or exchanges — it would risk
    arg collisions with the pre-declared definitions. It publishes to the events
    exchange and consumes from queues by name. Rejecting (`requeue=False`)
    naturally routes a message through the DLX to its DLQ.
    """

    EXCHANGE_NAME = "email_outreach.events"

    def __init__(self, url: str, prefetch: int = 10, exchange_name: str | None = None) -> None:
        self._url = url
        self._prefetch = prefetch
        self._exchange_name = exchange_name or os.getenv("RABBITMQ_EXCHANGE", self.EXCHANGE_NAME)
        self._conn: AbstractRobustConnection | None = None
        self._channel: AbstractRobustChannel | None = None
        self._exchange: AbstractExchange | None = None
        self._consumer_tasks: list[asyncio.Task[None]] = []

    async def _get_channel(self) -> AbstractRobustChannel:
        if self._channel is None or self._channel.is_closed:
            self._conn = await aio_pika.connect_robust(self._url)
            self._channel = await self._conn.channel()
            await self._channel.set_qos(prefetch_count=self._prefetch)
        return self._channel

    async def _get_exchange(self) -> AbstractExchange:
        if self._exchange is None:
            channel = await self._get_channel()
            self._exchange = await channel.get_exchange(self._exchange_name, ensure=True)
        return self._exchange

    async def publish(self, topic: str, message: dict[str, Any]) -> None:
        exchange = await self._get_exchange()
        body = json.dumps(message).encode("utf-8")
        await exchange.publish(
            aio_pika.Message(body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key=topic,
        )

    async def subscribe(self, topic: str, handler: MessageHandler) -> None:
        channel = await self._get_channel()
        queue = await channel.get_queue(topic, ensure=True)
        task = asyncio.create_task(self._consume(queue, handler), name=f"consume-{topic}")
        self._consumer_tasks.append(task)

    async def _consume(self, queue: AbstractRobustQueue, handler: MessageHandler) -> None:
        async with queue.iterator() as it:
            async for message in it:
                try:
                    payload = json.loads(message.body)
                except json.JSONDecodeError:
                    log.exception("malformed json on %s, sending to DLQ", queue.name)
                    await message.reject(requeue=False)
                    continue

                try:
                    await handler(payload)
                    await message.ack()
                except NonRetryableError:
                    log.exception("non-retryable error on %s, sending to DLQ", queue.name)
                    await message.reject(requeue=False)
                except Exception:
                    log.exception("handler failed on %s, sending to DLQ", queue.name)
                    await message.reject(requeue=False)

    async def disconnect(self) -> None:
        for task in self._consumer_tasks:
            task.cancel()
        for task in self._consumer_tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._consumer_tasks.clear()
        if self._channel is not None and not self._channel.is_closed:
            await self._channel.close()
        if self._conn is not None and not self._conn.is_closed:
            await self._conn.close()
        self._channel = None
        self._conn = None
        self._exchange = None
