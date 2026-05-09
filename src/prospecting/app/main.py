from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from .broker import BrokerConfig, RabbitBroker
from .config import Settings
from .db import Mongo, MongoConfig
from .worker import ProspectingWorker


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("prospecting")


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
            logger.info("consuming queue=%s", "sourcing.completed")

            def _handler(msg: dict) -> None:
                out = self.worker.handle_sourcing_completed(msg)
                self.broker.publish("prospecting.completed", out)

            self.broker.consume_forever(queue_name="sourcing.completed", handler=_handler)

        self._consumer_thread = threading.Thread(target=_run, name="consumer", daemon=True)
        self._consumer_thread.start()

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

