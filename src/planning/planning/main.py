from contextlib import asynccontextmanager
from functools import partial
from typing import AsyncIterator

import structlog
import uvicorn
from fastapi import FastAPI, Response

from local_infrastructure.factory.broker_factory import create_broker

from .config import settings
from .handlers import handle_plan_requested
from .llm import generate_plan
from .logging_setup import configure_logging
from .repository import PlanRepository

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.log_level)
    log.info(
        "planning service starting",
        broker=settings.broker_type,
        mongo_db=settings.mongo_db,
        llm_model=settings.llm_model,
    )

    repo = PlanRepository(settings.mongo_url, settings.mongo_db)
    await repo.bootstrap_indexes()

    broker = create_broker()
    handler = partial(handle_plan_requested, repo=repo, llm_fn=generate_plan, broker=broker)
    await broker.subscribe(settings.plan_requested_queue, handler)
    log.info("subscribed to queue", queue=settings.plan_requested_queue)

    app.state.repo = repo
    app.state.broker = broker
    try:
        yield
    finally:
        log.info("planning service shutting down")
        try:
            await broker.disconnect()
        finally:
            await repo.close()


app = FastAPI(title="Planning Service", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready(response: Response) -> dict[str, object]:
    repo: PlanRepository = app.state.repo
    mongo_ok = await repo.ping()
    ok = mongo_ok
    response.status_code = 200 if ok else 503
    return {"status": "ok" if ok else "degraded", "checks": {"mongo": mongo_ok}}


def run() -> None:
    uvicorn.run(
        "planning.main:app",
        host="0.0.0.0",
        port=settings.health_port,
        log_config=None,  # we configure structlog ourselves
    )


if __name__ == "__main__":
    run()
