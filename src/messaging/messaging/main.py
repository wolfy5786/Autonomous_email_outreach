import uuid
from contextlib import asynccontextmanager
from functools import partial
from typing import Any, AsyncIterator

import structlog
import uvicorn
from fastapi import FastAPI, Response

from local_infrastructure.factory.broker_factory import create_broker
from shared.models import init_db
from shared.observability import MongoTraceSink, set_trace_sink, trace_operation

from .config import settings
from .credentials import (
    CredentialsResolver,
    CredentialsResolverProtocol,
    StubCredentialsResolver,
)
from .handlers import handle_messaging_requested
from .llm import generate_draft
from .logging_setup import configure_logging
from .providers import create_provider
from .repository import MessagingRepository

log = structlog.get_logger(__name__)


def _build_credentials() -> CredentialsResolverProtocol:
    """Pick the right resolver for the configured provider."""
    if settings.email_provider == "gmail":
        if not settings.gmail_client_id or not settings.gmail_client_secret:
            raise RuntimeError(
                "EMAIL_PROVIDER=gmail requires GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET"
            )
        return CredentialsResolver(
            client_id=settings.gmail_client_id,
            client_secret=settings.gmail_client_secret,
        )
    return StubCredentialsResolver()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.log_level)
    log.info(
        "messaging service starting",
        broker=settings.broker_type,
        mongo_db=settings.mongo_db,
        llm_model=settings.llm_model,
        email_provider=settings.email_provider,
    )

    # Mongo + Beanie. init_beanie creates the (campaign_id, poc_id) unique
    # index on email_drafts that the repo relies on for idempotency.
    mongo_client, db = await init_db(
        connection_string=settings.mongo_url,
        database_name=settings.mongo_db,
    )
    repo = MessagingRepository(db)
    # Trace sink: every trace_operation in this process writes TraceEvent rows to Mongo.
    set_trace_sink(MongoTraceSink())

    credentials = _build_credentials()
    provider = create_provider()
    broker = create_broker()

    inner_handler = partial(
        handle_messaging_requested,
        repo=repo,
        llm_fn=generate_draft,
        provider=provider,
        credentials=credentials,
        broker=broker,
        settings=settings,
    )

    async def traced_handler(msg: dict[str, Any]) -> None:
        """Wrap the real handler with START/END/ERROR trace events."""
        trace_id = msg.get("trace_id") or str(uuid.uuid4())
        campaign_id = msg.get("campaign_id")
        async with trace_operation(
            trace_id=trace_id,
            campaign_id=campaign_id,
            service="messaging",
            event_name="messaging.requested.consume",
            metadata={"queue": settings.messaging_requested_queue},
        ):
            await inner_handler(msg)

    await broker.subscribe(settings.messaging_requested_queue, traced_handler)
    log.info("subscribed to queue", queue=settings.messaging_requested_queue)

    app.state.repo = repo
    app.state.broker = broker
    app.state.mongo_client = mongo_client
    try:
        yield
    finally:
        log.info("messaging service shutting down")
        try:
            await broker.disconnect()
        finally:
            mongo_client.close()


app = FastAPI(title="Messaging Service", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready(response: Response) -> dict[str, object]:
    repo: MessagingRepository = app.state.repo
    mongo_ok = await repo.ping()
    response.status_code = 200 if mongo_ok else 503
    return {"status": "ok" if mongo_ok else "degraded", "checks": {"mongo": mongo_ok}}


def run() -> None:
    uvicorn.run(
        "messaging.main:app",
        host="0.0.0.0",
        port=settings.health_port,
        log_config=None,  # we configure structlog ourselves
    )


if __name__ == "__main__":
    run()
