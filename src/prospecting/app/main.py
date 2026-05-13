from __future__ import annotations

import json
import logging
import structlog
import threading
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Response
from pika.exceptions import AMQPError
from pymongo.errors import PyMongoError
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

from .logging_setup import configure_logging

from .broker import BrokerConfig, RabbitBroker
from .config import Settings
from .db import Mongo, MongoConfig
from .errors import PermanentProcessingError, RetryableProcessingError
from .worker import ProspectingWorker


# Replaces logging.basicConfig — structlog → JSON, stamps service/env on every line.
configure_logging(service="prospecting")
logger = structlog.get_logger("prospecting").bind(service="prospecting")


MESSAGES_RECEIVED = Counter(
    "prospecting_messages_received",
    "Total prospecting.requested messages received by the service",
)
COMPLETED_PUBLISHED = Counter(
    "prospecting_completed_published",
    "Total prospecting.completed messages published by the service",
)
DUPLICATE_SKIPPED = Counter(
    "prospecting_duplicate_messages_skipped",
    "Total duplicate prospecting messages skipped via idempotency",
)
PERMANENT_FAILURES = Counter(
    "prospecting_permanent_failures",
    "Total non-retryable prospecting processing failures",
)
RETRYABLE_FAILURES = Counter(
    "prospecting_retryable_failures",
    "Total retryable prospecting processing failures",
)


# use structlog-bound logger for structured events


class AppState:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.mongo = Mongo(MongoConfig(uri=settings.mongodb_uri, db_name=settings.mongodb_db))
        self.broker = RabbitBroker(
            BrokerConfig(url=settings.rabbitmq_url, exchange=settings.rabbitmq_exchange, prefetch=settings.rabbitmq_prefetch)
        )
        self.worker = ProspectingWorker(mongo=self.mongo, default_min_icp_score=settings.default_min_icp_score)
        self._consumer_thread: threading.Thread | None = None

    def start(self) -> None:
        self.mongo.connect()
        self.broker.connect()

        def _run() -> None:
            logger.info("consuming", queue="prospecting.requested")

            self.broker.consume_forever(queue_name="prospecting.requested", handler=self.handle_prospecting_requested_message)

        self._consumer_thread = threading.Thread(target=_run, name="consumer", daemon=True)
        self._consumer_thread.start()

    def handle_prospecting_requested_message(self, msg: dict, props: object | None = None, method: object | None = None) -> None:
        # idempotency: skip already-processed events when event_id or idempotency_key is present
        MESSAGES_RECEIVED.inc()
        event_id = None
        try:
            event_id = msg.get("event_id") or msg.get("idempotency_key")
        except Exception:
            event_id = None

        campaign_id = None
        try:
            campaign_id = msg.get("campaign_id")
        except Exception:
            campaign_id = None

        plan_id = None
        try:
            plan_id = msg.get("plan_id")
        except Exception:
            plan_id = None

        entity_ids = []
        try:
            entity_ids = list(msg.get("entity_ids") or [])
        except Exception:
            entity_ids = []

        # log message received (minimal payload info)
        logger.info(
            "message_received",
            stage="message_received",
            status="received",
            campaign_id=campaign_id,
            plan_id=plan_id,
            event_id=event_id,
            idempotency_key=msg.get("idempotency_key"),
            trace_id=msg.get("trace_id"),
            entity_count=len(entity_ids),
            entity_ids_sample=entity_ids[:5],
        )

        retry_count = 0
        if props is not None:
            try:
                headers = getattr(props, "headers", None) or {}
                x_death = headers.get("x-death")
                if isinstance(x_death, list) and x_death:
                    retry_count = int(x_death[0].get("count", 0))
            except Exception:
                retry_count = 0

        if event_id and self.mongo.is_event_processed(event_id, campaign_id):
            DUPLICATE_SKIPPED.inc()
            logger.info(
                "idempotency_check",
                stage="idempotency_check",
                status="duplicate_skipped",
                campaign_id=campaign_id,
                plan_id=plan_id,
                event_id=event_id,
                idempotency_key=msg.get("idempotency_key"),
                trace_id=msg.get("trace_id"),
                retry_count=retry_count,
            )
            return

        try:
            out = self.worker.handle_prospecting_requested(msg)
        except PermanentProcessingError as exc:
            PERMANENT_FAILURES.inc()
            logger.error(
                "worker_completed",
                stage="worker_completed",
                status="failed",
                campaign_id=campaign_id,
                plan_id=plan_id,
                event_id=event_id,
                idempotency_key=msg.get("idempotency_key"),
                trace_id=msg.get("trace_id"),
                error_type=type(exc).__name__,
                error_message=str(exc),
                retry_count=retry_count,
            )
            raise
        except PyMongoError as exc:
            RETRYABLE_FAILURES.inc()
            logger.error(
                "worker_completed",
                stage="worker_completed",
                status="retrying",
                campaign_id=campaign_id,
                plan_id=plan_id,
                event_id=event_id,
                idempotency_key=msg.get("idempotency_key"),
                trace_id=msg.get("trace_id"),
                error_type=type(exc).__name__,
                error_message=str(exc),
                retry_count=retry_count,
            )
            raise RetryableProcessingError(str(exc)) from exc

        # publish only after DB writes inside the worker have completed
        try:
            # worker success — include ranked_count
            ranked_count = 0
            try:
                ranked_count = len(out.get("ranked_prospects") or [])
            except Exception:
                ranked_count = 0

            logger.info(
                "worker_completed",
                stage="worker_completed",
                status="success",
                campaign_id=campaign_id,
                plan_id=plan_id,
                event_id=event_id,
                idempotency_key=msg.get("idempotency_key"),
                trace_id=msg.get("trace_id"),
                ranked_count=ranked_count,
            )

            self.broker.publish("prospecting.completed", out)
            COMPLETED_PUBLISHED.inc()

            logger.info(
                "publish_completed",
                stage="publish_completed",
                status="published",
                campaign_id=campaign_id,
                plan_id=plan_id,
                event_id=event_id,
                idempotency_key=msg.get("idempotency_key"),
                trace_id=msg.get("trace_id"),
                ranked_count=ranked_count,
            )
        except AMQPError as exc:
            RETRYABLE_FAILURES.inc()
            logger.error(
                "publish_completed",
                stage="publish_completed",
                status="retrying",
                campaign_id=campaign_id,
                plan_id=plan_id,
                event_id=event_id,
                idempotency_key=msg.get("idempotency_key"),
                trace_id=msg.get("trace_id"),
                error_type=type(exc).__name__,
                error_message=str(exc),
                retry_count=retry_count,
            )
            raise RetryableProcessingError(str(exc)) from exc

        # mark event processed so repeated messages are idempotent
        if event_id:
            try:
                self.mongo.mark_event_processed(event_id, campaign_id, payload=out)
            except Exception as exc:
                logger.error(
                    "idempotency_mark",
                    stage="idempotency_mark",
                    status="failed",
                    campaign_id=campaign_id,
                    plan_id=plan_id,
                    event_id=event_id,
                    idempotency_key=msg.get("idempotency_key"),
                    trace_id=msg.get("trace_id"),
                    error_type="mark_event_processed_failed",
                    error_message=str(exc),
                    retry_count=retry_count,
                )
                raise
            else:
                logger.info(
                    "idempotency_mark",
                    stage="idempotency_mark",
                    status="persisted",
                    campaign_id=campaign_id,
                    plan_id=plan_id,
                    event_id=event_id,
                    idempotency_key=msg.get("idempotency_key"),
                    trace_id=msg.get("trace_id"),
                    retry_count=retry_count,
                )

    def stop(self) -> None:
        try:
            self.broker.close()
        finally:
            self.mongo.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    state = AppState(settings)
    state.start()
    app.state.state = state
    yield
    state.stop()


app = FastAPI(title="prospecting", lifespan=lifespan)


@app.get("/health")
def health():
    state: AppState = app.state.state
    return {
        "ok": True,
        "broker_connected": state.broker.is_connected,
        "mongodb_db": state.settings.mongodb_db,
    }


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def main() -> None:
    settings = Settings()
    uvicorn.run(
        "app.main:app",
        host=settings.http_host,
        port=settings.http_port,
        reload=False,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()

