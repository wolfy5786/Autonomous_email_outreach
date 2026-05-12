from __future__ import annotations

import json
import logging
import threading
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from pika.exceptions import AMQPError
from pymongo.errors import PyMongoError

from .broker import BrokerConfig, RabbitBroker
from .config import Settings
from .db import Mongo, MongoConfig
from .errors import PermanentProcessingError, RetryableProcessingError
from .worker import ProspectingWorker


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("prospecting")


def _structured_log(level: int, **fields: object) -> None:
    logger.log(level, json.dumps(fields, sort_keys=True, separators=(",", ":")))


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
            logger.info("consuming queue=%s", "prospecting.requested")

            self.broker.consume_forever(queue_name="prospecting.requested", handler=self.handle_prospecting_requested_message)

        self._consumer_thread = threading.Thread(target=_run, name="consumer", daemon=True)
        self._consumer_thread.start()

    def handle_prospecting_requested_message(self, msg: dict, props: object | None = None, method: object | None = None) -> None:
        # idempotency: skip already-processed events when event_id or idempotency_key is present
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
            _structured_log(
                logging.INFO,
                service="prospecting",
                campaign_id=campaign_id,
                event_id=event_id,
                idempotency_key=msg.get("idempotency_key"),
                trace_id=msg.get("trace_id"),
                status="duplicate_skipped",
                error_type=None,
                retry_count=retry_count,
            )
            return

        try:
            out = self.worker.handle_prospecting_requested(msg)
        except PermanentProcessingError as exc:
            _structured_log(
                logging.ERROR,
                service="prospecting",
                campaign_id=campaign_id,
                event_id=event_id,
                idempotency_key=msg.get("idempotency_key"),
                trace_id=msg.get("trace_id"),
                status="failed",
                error_type=type(exc).__name__,
                retry_count=retry_count,
            )
            raise
        except PyMongoError as exc:
            _structured_log(
                logging.ERROR,
                service="prospecting",
                campaign_id=campaign_id,
                event_id=event_id,
                idempotency_key=msg.get("idempotency_key"),
                trace_id=msg.get("trace_id"),
                status="retrying",
                error_type=type(exc).__name__,
                retry_count=retry_count,
            )
            raise RetryableProcessingError(str(exc)) from exc

        # publish only after DB writes inside the worker have completed
        try:
            self.broker.publish("prospecting.completed", out)
        except AMQPError as exc:
            _structured_log(
                logging.ERROR,
                service="prospecting",
                campaign_id=campaign_id,
                event_id=event_id,
                idempotency_key=msg.get("idempotency_key"),
                trace_id=msg.get("trace_id"),
                status="retrying",
                error_type=type(exc).__name__,
                retry_count=retry_count,
            )
            raise RetryableProcessingError(str(exc)) from exc

        # mark event processed so repeated messages are idempotent
        if event_id:
            try:
                self.mongo.mark_event_processed(event_id, campaign_id, payload=out)
            except Exception:
                _structured_log(
                    logging.ERROR,
                    service="prospecting",
                    campaign_id=campaign_id,
                    event_id=event_id,
                    idempotency_key=msg.get("idempotency_key"),
                    trace_id=msg.get("trace_id"),
                    status="failed",
                    error_type="mark_event_processed_failed",
                    retry_count=retry_count,
                )
                raise

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


def main() -> None:
    settings = Settings()
    uvicorn.run("app.main:app", host=settings.http_host, port=settings.http_port, reload=False, log_level="info")


if __name__ == "__main__":
    main()

