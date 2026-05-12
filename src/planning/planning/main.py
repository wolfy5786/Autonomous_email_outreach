from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

import structlog
import uvicorn
from fastapi import FastAPI, Response

from .config import settings
from .handlers import handle_plan_requested
from .llm import generate_plan
from .logging_setup import configure_logging
from .repository import PlanRepository
from .subscriber import PlanningAMQPClient, _safe_broker_host

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.log_level)
    log.info(
        "planning service starting",
        module=__name__,
        mongo_db=settings.mongo_db,
        llm_model=settings.llm_model,
        rabbitmq_exchange=settings.rabbitmq_exchange,
        plan_requested_queue=settings.plan_requested_queue,
        broker_host=_safe_broker_host(settings.rabbitmq_url),
    )

    repo = PlanRepository(settings.mongo_url, settings.mongo_db)
    await repo.bootstrap_indexes()

    amqp = PlanningAMQPClient(settings)
    await amqp.connect()
    handler = partial(handle_plan_requested, repo=repo, llm_fn=generate_plan, publisher=amqp)
    await amqp.start_consumer(handler)
    log.info("subscribed to queue", module=__name__, queue=settings.plan_requested_queue)

    app.state.repo = repo
    app.state.amqp_client = amqp
    try:
        yield
    finally:
        log.info("planning service shutting down", module=__name__)
        try:
            await amqp.disconnect()
        except Exception:
            log.error("planning service amqp disconnect failed", module=__name__, exc_info=True)
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
