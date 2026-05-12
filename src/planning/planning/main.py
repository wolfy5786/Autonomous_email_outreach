from contextlib import asynccontextmanager
from functools import partial
from typing import AsyncIterator

import structlog
import uvicorn
from fastapi import FastAPI, Response

from local_infrastructure.factory.broker_factory import create_broker
from shared.models.db import init_db
from shared.observability import MongoTraceSink, configure_logging, set_trace_sink

from .config import settings
from .handlers import handle_plan_requested
from .llm import generate_plan
from .repository import PlanRepository

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(service="planning", level=settings.log_level)
    log.info(
        "planning service starting",
        broker=settings.broker_type,
        mongo_db=settings.mongo_db,
        llm_model=settings.llm_model,
    )

    repo = PlanRepository(settings.mongo_url, settings.mongo_db)
    await repo.bootstrap_indexes()

    # Initialize Beanie ODM for shared models (registers TraceEvent collection too)
    # and activate the Mongo trace sink so every publish/consume is persisted.
    mongo_client, _ = await init_db(settings.mongo_url, settings.mongo_db)
    set_trace_sink(MongoTraceSink())

    broker = create_broker()
    handler = partial(handle_plan_requested, repo=repo, llm_fn=generate_plan, broker=broker)
    await broker.subscribe(settings.plan_requested_queue, handler)
    log.info("subscribed to queue", queue=settings.plan_requested_queue)

    app.state.repo = repo
    app.state.broker = broker
    app.state.mongo_client = mongo_client
    try:
        yield
    finally:
        log.info("planning service shutting down")
        set_trace_sink(None)
        try:
            await broker.disconnect()
        finally:
            await repo.close()
            mongo_client.close()


app = FastAPI(title="Planning Service", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready(response: Response) -> dict[str, object]:
    repo: PlanRepository = app.state.repo
    mongo_ok = await repo.ping()
    broker_ok = await app.state.broker.ping()
    ok = mongo_ok and broker_ok
    response.status_code = 200 if ok else 503
    return {
        "status": "ok" if ok else "degraded",
        "checks": {"mongo": mongo_ok, "broker": broker_ok},
    }


def run() -> None:
    uvicorn.run(
        "planning.main:app",
        host="0.0.0.0",
        port=settings.health_port,
        log_config=None,  # we configure structlog ourselves
    )


if __name__ == "__main__":
    run()
