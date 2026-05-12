from contextlib import asynccontextmanager
from functools import partial
from typing import AsyncIterator

import structlog
import uvicorn
from fastapi import FastAPI, Response

from local_infrastructure.factory.broker_factory import create_broker
from shared.models import init_db
from shared.observability import MongoTraceSink, configure_logging, set_trace_sink

from .config import settings
from .credentials import (
    CredentialsResolver,
    CredentialsResolverProtocol,
    StubCredentialsResolver,
)
from .handlers import handle_messaging_requested
from .llm import generate_draft
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
    configure_logging(service="messaging", level=settings.log_level)
    log.info(
        "messaging service starting",
        broker=settings.broker_type,
        mongo_db=settings.mongo_db,
        llm_model=settings.llm_model,
        email_provider=settings.email_provider,
    )

    # Mongo + Beanie. init_beanie creates the (campaign_id, poc_id) unique
    # index on email_drafts that the repo relies on for idempotency. The same
    # init_db also registers the trace_events collection used by MongoTraceSink.
    mongo_client, db = await init_db(
        connection_string=settings.mongo_url,
        database_name=settings.mongo_db,
    )
    repo = MessagingRepository(db)
    set_trace_sink(MongoTraceSink())

    credentials = _build_credentials()
    provider = create_provider()
    broker = create_broker()

    handler = partial(
        handle_messaging_requested,
        repo=repo,
        llm_fn=generate_draft,
        provider=provider,
        credentials=credentials,
        broker=broker,
        settings=settings,
    )
    await broker.subscribe(settings.messaging_requested_queue, handler)
    log.info("subscribed to queue", queue=settings.messaging_requested_queue)

    app.state.repo = repo
    app.state.broker = broker
    app.state.mongo_client = mongo_client
    try:
        yield
    finally:
        log.info("messaging service shutting down")
        set_trace_sink(None)
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
    broker_ok = await app.state.broker.ping()
    ok = mongo_ok and broker_ok
    response.status_code = 200 if ok else 503
    return {
        "status": "ok" if ok else "degraded",
        "checks": {"mongo": mongo_ok, "broker": broker_ok},
    }


def run() -> None:
    uvicorn.run(
        "messaging.main:app",
        host="0.0.0.0",
        port=settings.health_port,
        log_config=None,  # we configure structlog ourselves
    )


if __name__ == "__main__":
    run()
