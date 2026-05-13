from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

import pika
import structlog
from pika.adapters.blocking_connection import BlockingChannel

from .errors import MalformedMessageError, PermanentProcessingError, RetryableProcessingError


logger = structlog.get_logger("prospecting.broker").bind(service="prospecting")


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

        MAX_RETRIES = 3
        # MAX_RETRIES=3 means 3 retry attempts after initial attempt (4 total attempts)
        # Semantics: initial attempt (retry_count=0), then retries 1,2,3; on 4th attempt (next_retry_cnt=4), dead-letter
        RETRY_DELAY_MS = 5000  # 5 seconds before retry
        retry_queue = f"{queue_name}.retry"
        dlq = f"{queue_name}.dlq"

        # Declare retry queue with TTL and dead-letter back to main queue
        self._ch.queue_declare(queue=retry_queue, durable=True, arguments={
            "x-message-ttl": RETRY_DELAY_MS,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": queue_name,
        })

        # Declare DLQ
        self._ch.queue_declare(queue=dlq, durable=True)

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
                "campaign_id": (msg or {}).get("campaign_id"),
                "event_id": (msg or {}).get("event_id"),
                "idempotency_key": (msg or {}).get("idempotency_key"),
                "trace_id": (msg or {}).get("trace_id"),
                "retry_count": _retry_count(props),
            }

        def _send_to_dlq(msg: dict[str, Any] | None, props: Any, error_type: str, error_message: str) -> None:
            """Send message to DLQ after max retries exceeded."""
            context = _message_context(msg, props)
            context.update({
                "queue": queue_name,
                "stage": "handler_max_retries_exceeded",
                "status": "dead_lettered",
                "error_type": error_type,
                "error_message": error_message,
                "max_retries": MAX_RETRIES,
                "retry_count": _retry_count(props),
            })
            logger.error("dead_lettered", **context)
            try:
                body = json.dumps(msg or {}, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
                self._ch.basic_publish(
                    exchange="",
                    routing_key=dlq,
                    body=body,
                    properties=pika.BasicProperties(
                        content_type="application/json",
                        delivery_mode=2,
                        headers={"error_type": error_type, "error_message": error_message},
                    ),
                )
            except Exception as exc:
                logger.error("dlq_publish_failed", error=str(exc))

        def _nack(ch: BlockingChannel, delivery_tag: Any, msg: dict[str, Any] | None, props: Any, error_type: str, status: str, error_message: str, stage: str, error_code: str = None) -> None:
            context = _message_context(msg, props)
            context.update({
                "queue": queue_name,
                "stage": stage,
                "status": status,
                "error_type": error_type,
                "error_message": error_message,
                "error_code": error_code,
                "requeue": False,
            })
            logger.error("handler_error", **context)
            ch.basic_nack(delivery_tag=delivery_tag, requeue=False)

        def _on_message(ch: BlockingChannel, method: Any, props: Any, body: bytes) -> None:
            msg: dict[str, Any] | None = None
            try:
                msg = json.loads(body.decode("utf-8"))
                if not isinstance(msg, dict):
                    raise MalformedMessageError("message must be a JSON object")
                handler(msg, props, method)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except MalformedMessageError as exc:
                error_msg = str(exc)
                _nack(ch, method.delivery_tag, msg, props, type(exc).__name__, "rejected", error_msg, "message_decode", error_code="invalid_json")
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except PermanentProcessingError as exc:
                error_msg = str(exc)
                _nack(ch, method.delivery_tag, msg, props, type(exc).__name__, "failed", error_msg, "handler_permanent_error")
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except RetryableProcessingError as exc:
                error_msg = str(exc)
                retry_cnt = _retry_count(props)
                next_retry_cnt = retry_cnt + 1
                if next_retry_cnt > MAX_RETRIES:
                    # exceeded max retries; send to DLQ
                    _send_to_dlq(msg, props, type(exc).__name__, error_msg)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                else:
                    # republish to retry queue with incremented retry count
                    context = _message_context(msg, props)
                    context.update({
                        "queue": queue_name,
                        "stage": "handler_retryable_error",
                        "status": "retry_scheduled",
                        "error_type": type(exc).__name__,
                        "error_message": error_msg,
                        "max_retries": MAX_RETRIES,
                        "retry_count": next_retry_cnt,
                        "requeue": False,
                        "republished": True,
                    })
                    logger.warning("retry_scheduled", **context)
                    try:
                        body = json.dumps(msg or {}, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
                        # Copy existing headers and increment retry count
                        headers = dict(getattr(props, "headers", None) or {})
                        headers["x-retry-count"] = next_retry_cnt
                        headers["x-original-error"] = error_msg
                        headers["x-last-error-type"] = type(exc).__name__
                        self._ch.basic_publish(
                            exchange="",
                            routing_key=retry_queue,
                            body=body,
                            properties=pika.BasicProperties(
                                content_type="application/json",
                                delivery_mode=2,
                                headers=headers,
                            ),
                        )
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                    except Exception as send_exc:
                        logger.error("retry_queue_publish_failed", error=str(send_exc))
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            except Exception as exc:
                error_msg = str(exc)
                _nack(ch, method.delivery_tag, msg, props, type(exc).__name__, "failed", error_msg, "unexpected_error")
                ch.basic_ack(delivery_tag=method.delivery_tag)

        self._ch.basic_consume(queue=queue_name, on_message_callback=_on_message)
        self._ch.start_consuming()

