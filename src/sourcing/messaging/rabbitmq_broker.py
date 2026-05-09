"""RabbitMQ (AMQP) implementation of the broker contract using pika."""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

import pika
from pika.adapters.blocking_connection import BlockingChannel, BlockingConnection

from messaging.broker_interface import BrokerInterface, MessageCallback

logger = logging.getLogger(__name__)

# Used only when RABBITMQ_URL is unset or empty (e.g. quick local broker on localhost).
DEFAULT_RABBITMQ_URL = "amqp://guest:guest@localhost:5672/%2F"
DEFAULT_CONNECT_RETRIES = 30
DEFAULT_CONNECT_BACKOFF_S = 2.0


class RabbitmqBroker(BrokerInterface):
    """Blocking pika client with manual consumer acks."""

    def __init__(self) -> None:
        raw = os.environ.get("RABBITMQ_URL", "").strip()
        self._url: str = raw or DEFAULT_RABBITMQ_URL
        self._connection: Optional[BlockingConnection] = None
        self._channel: Optional[BlockingChannel] = None

    def connect(self) -> None:
        if self._connection and not self._connection.is_closed:
            return

        retries = int(os.environ.get("RABBITMQ_CONNECT_RETRIES", DEFAULT_CONNECT_RETRIES))
        backoff = float(os.environ.get("RABBITMQ_CONNECT_BACKOFF_S", DEFAULT_CONNECT_BACKOFF_S))

        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                params = pika.URLParameters(self._url)
                self._connection = pika.BlockingConnection(params)
                self._channel = self._connection.channel()
                # Fair dispatch for multiple consumers in the future
                self._channel.basic_qos(prefetch_count=1)
                logger.info("Connected to RabbitMQ (attempt %s/%s).", attempt, retries)
                return
            except Exception as e:
                last_error = e
                logger.warning(
                    "RabbitMQ connect failed (attempt %s/%s): %s. Retrying in %ss...",
                    attempt,
                    retries,
                    e,
                    backoff,
                )
                time.sleep(backoff)

        assert last_error is not None
        logger.error("Giving up connecting to RabbitMQ after %s attempts.", retries)
        raise last_error

    def publish(self, exchange: str, routing_key: str, body: bytes) -> None:
        if not self._channel or self._channel.is_closed:
            raise RuntimeError("Broker is not connected; call connect() first.")
        self._channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=body,
            properties=pika.BasicProperties(delivery_mode=2),  # persistent
        )

    def subscribe(self, queue: str, callback: MessageCallback) -> None:
        if not self._channel or self._channel.is_closed:
            raise RuntimeError("Broker is not connected; call connect() first.")

        ch = self._channel

        def _on_message(
            _ch: BlockingChannel,
            method: pika.spec.Basic.Deliver,
            _properties: pika.spec.BasicProperties,
            body: bytes,
        ) -> None:
            try:
                callback(body)
                _ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception:
                logger.exception("Message handler failed; nack (no requeue) — message may go to DLQ.")
                _ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        ch.basic_consume(queue=queue, on_message_callback=_on_message, auto_ack=False)
        logger.info("Subscribed to queue %r; waiting for messages...", queue)
        ch.start_consuming()

    def close(self) -> None:
        if self._channel and not self._channel.is_closed:
            try:
                self._channel.stop_consuming()
            except Exception as e:
                logger.debug("stop_consuming: %s", e)
        self._channel = None
        if self._connection and not self._connection.is_closed:
            self._connection.close()
        self._connection = None
        logger.info("RabbitMQ connection closed.")

    def request_stop(self) -> None:
        """Unblock a running consumer (safe to call from a SIGINT/SIGTERM handler)."""
        if self._channel and not self._channel.is_closed:
            self._channel.stop_consuming()
