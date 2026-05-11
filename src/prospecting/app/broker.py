from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable

import pika
from pika.adapters.blocking_connection import BlockingChannel

from .errors import MalformedMessageError, PermanentProcessingError, RetryableProcessingError


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

    def consume_forever(self, queue_name: str, handler: Callable[[dict[str, Any], Any, Any], None]) -> None:
        if not self._ch:
            raise RuntimeError("broker not connected")

        def _retry_count(props: Any) -> int:
            headers = getattr(props, "headers", None) or {}
            x_death = headers.get("x-death")
            if isinstance(x_death, list) and x_death:
                try:
                    return int(x_death[0].get("count", 0))
                except Exception:
                    return 0
            for key in ("retry_count", "x-retry-count"):
                if key in headers:
                    try:
                        return int(headers[key])
                    except Exception:
                        return 0
            return 0

        def _message_context(msg: dict[str, Any] | None, props: Any) -> dict[str, Any]:
            headers = getattr(props, "headers", None) or {}
            return {
                "service": "prospecting",
                "campaign_id": (msg or {}).get("campaign_id"),
                "event_id": (msg or {}).get("event_id"),
                "idempotency_key": (msg or {}).get("idempotency_key"),
                "trace_id": (msg or {}).get("trace_id"),
                "retry_count": _retry_count(props),
                "x_death": headers.get("x-death"),
            }

        def _nack(ch: BlockingChannel, delivery_tag: Any, requeue: bool, msg: dict[str, Any] | None, props: Any, error_type: str, status: str) -> None:
            logger.error(json.dumps({**_message_context(msg, props), "status": status, "error_type": error_type}, sort_keys=True, separators=(",", ":")))
            ch.basic_nack(delivery_tag=delivery_tag, requeue=requeue)

        def _on_message(ch: BlockingChannel, method: Any, props: Any, body: bytes) -> None:
            msg: dict[str, Any] | None = None
            try:
                msg = json.loads(body.decode("utf-8"))
                if not isinstance(msg, dict):
                    raise MalformedMessageError("message must be a JSON object")
                handler(msg, props, method)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except MalformedMessageError as exc:
                _nack(ch, method.delivery_tag, False, msg, props, type(exc).__name__, "rejected")
            except PermanentProcessingError as exc:
                _nack(ch, method.delivery_tag, False, msg, props, type(exc).__name__, "failed")
            except RetryableProcessingError as exc:
                _nack(ch, method.delivery_tag, True, msg, props, type(exc).__name__, "retrying")
            except Exception as exc:
                _nack(ch, method.delivery_tag, False, msg, props, type(exc).__name__, "failed")

        self._ch.basic_consume(queue=queue_name, on_message_callback=_on_message)
        self._ch.start_consuming()

