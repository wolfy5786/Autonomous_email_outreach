from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable

import pika
from pika.adapters.blocking_connection import BlockingChannel


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BrokerConfig:
    url: str
    exchange: str
    prefetch: int = 10


class RabbitBroker:
    def __init__(self, cfg: BrokerConfig):
        self._cfg = cfg
        self._conn: pika.BlockingConnection | None = None
        self._ch: BlockingChannel | None = None

    def connect(self) -> None:
        params = pika.URLParameters(self._cfg.url)
        self._conn = pika.BlockingConnection(params)
        self._ch = self._conn.channel()
        self._ch.basic_qos(prefetch_count=self._cfg.prefetch)

    def close(self) -> None:
        try:
            if self._ch and self._ch.is_open:
                self._ch.close()
        finally:
            if self._conn and self._conn.is_open:
                self._conn.close()

    @property
    def is_connected(self) -> bool:
        return bool(self._conn and self._conn.is_open and self._ch and self._ch.is_open)

    def publish(self, routing_key: str, payload: dict[str, Any]) -> None:
        if not self._ch:
            raise RuntimeError("broker not connected")
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self._ch.basic_publish(
            exchange=self._cfg.exchange,
            routing_key=routing_key,
            body=body,
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,  # persistent
            ),
        )

    def consume_forever(self, queue_name: str, handler: Callable[[dict[str, Any]], None]) -> None:
        if not self._ch:
            raise RuntimeError("broker not connected")

        def _on_message(ch: BlockingChannel, method: Any, _props: Any, body: bytes) -> None:
            try:
                msg = json.loads(body.decode("utf-8"))
                if not isinstance(msg, dict):
                    raise ValueError("message must be a JSON object")
                handler(msg)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception:
                logger.exception("failed processing message from %s", queue_name)
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        self._ch.basic_consume(queue=queue_name, on_message_callback=_on_message)
        self._ch.start_consuming()

