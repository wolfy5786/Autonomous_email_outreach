import asyncio
import json
import logging
from typing import Any

import aio_pika
from aio_pika.abc import AbstractRobustChannel, AbstractRobustConnection, AbstractRobustQueue

from local_infrastructure.factory.broker_interface import MessageBroker, MessageHandler, NonRetryableError

log = logging.getLogger(__name__)


class RabbitMQBroker(MessageBroker):
    """aio-pika adapter.

    Queues are durable; each topic X also declares a sibling DLQ X.dlq.
    Messages are dead-lettered (never requeued) on parse errors, NonRetryableError,
    and uncaught handler exceptions — we rely on tenacity inside handlers to cover
    transient failures, so redelivery loops never form.
    """

    def __init__(self, url: str, prefetch: int = 10) -> None:
        self._url = url
        self._prefetch = prefetch
        self._conn: AbstractRobustConnection | None = None
        self._channel: AbstractRobustChannel | None = None
        self._consumer_tasks: list[asyncio.Task[None]] = []

    async def _get_channel(self) -> AbstractRobustChannel:
        if self._channel is None or self._channel.is_closed:
            self._conn = await aio_pika.connect_robust(self._url)
            self._channel = await self._conn.channel()
            await self._channel.set_qos(prefetch_count=self._prefetch)
        return self._channel

    async def _declare_queue(self, channel: AbstractRobustChannel, topic: str) -> AbstractRobustQueue:
        dlq_name = f"{topic}.dlq"
        # Sibling DLQ — durable, no dead-letter of its own.
        await channel.declare_queue(dlq_name, durable=True)
        return await channel.declare_queue(
            topic,
            durable=True,
            arguments={
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": dlq_name,
            },
        )

    async def publish(self, topic: str, message: dict[str, Any]) -> None:
        channel = await self._get_channel()
        await self._declare_queue(channel, topic)
        body = json.dumps(message).encode("utf-8")
        await channel.default_exchange.publish(
            aio_pika.Message(body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key=topic,
        )

    async def subscribe(self, topic: str, handler: MessageHandler) -> None:
        channel = await self._get_channel()
        queue = await self._declare_queue(channel, topic)
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
