import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial
from typing import Any

import structlog
import uvicorn
from fastapi import FastAPI, Response

from shared.models.db import init_db
from shared.observability import MongoTraceSink, set_trace_sink, trace_operation

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
        sourcing_requested_queue=settings.sourcing_requested_queue,
        broker_host=_safe_broker_host(settings.rabbitmq_url),
    )

    repo = PlanRepository(settings.mongo_url, settings.mongo_db)
    await repo.bootstrap_indexes()

    # Beanie init for shared models (registers TraceEvent collection). Opens a
    # second Motor client to the same Mongo as the repo — wasteful but keeps
    # the two access paths (Motor-direct vs Beanie) cleanly separated.
    mongo_client_beanie, _ = await init_db(settings.mongo_url, settings.mongo_db)
    set_trace_sink(MongoTraceSink())

    amqp = PlanningAMQPClient(settings)
    await amqp.connect()
    inner_handler = partial(handle_plan_requested, repo=repo, llm_fn=generate_plan, publisher=amqp)

    async def traced_handler(msg: dict[str, Any]) -> None:
        """Wrap the real handler with START/END/ERROR trace events."""
        trace_id = msg.get("trace_id") or str(uuid.uuid4())
        campaign_id = msg.get("campaign_id")
        async with trace_operation(
            trace_id=trace_id,
            campaign_id=campaign_id,
            service="planning",
            event_name="plan.requested.consume",
            metadata={"queue": settings.plan_requested_queue},
        ):
            await inner_handler(msg)

    await amqp.start_consumer(traced_handler)
    log.info("subscribed to queue", module=__name__, queue=settings.plan_requested_queue)

    app.state.repo = repo
    app.state.amqp_client = amqp
    app.state.mongo_client_beanie = mongo_client_beanie
    try:
        yield
    finally:
        log.info("planning service shutting down", module=__name__)
        set_trace_sink(None)
        try:
            await amqp.disconnect()
        except Exception:
            log.error("planning service amqp disconnect failed", module=__name__, exc_info=True)
        finally:
            await repo.close()
            try:
                mongo_client_beanie.close()
            except Exception:
                log.error("beanie mongo client close failed", module=__name__, exc_info=True)


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
