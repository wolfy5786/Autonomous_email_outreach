"""FastAPI app for the observability service."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from shared.models.db import init_db
from shared.observability import configure_logging

from .config import settings
from .repository import TraceRepository

log = structlog.get_logger()

_TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(service="observability", level=settings.log_level)
    log.info(
        "observability service starting",
        mongo_db=settings.mongo_db,
    )

    mongo_client, db = await init_db(settings.mongo_url, settings.mongo_db)
    app.state.mongo_client = mongo_client
    app.state.repo = TraceRepository(db)

    try:
        yield
    finally:
        log.info("observability service shutting down")
        mongo_client.close()


app = FastAPI(title="Observability Service", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready(response: Response) -> dict[str, object]:
    """Ready when Mongo responds to a ping."""
    try:
        await app.state.mongo_client.admin.command("ping")
        mongo_ok = True
    except Exception:
        log.exception("mongo_ping_failed")
        mongo_ok = False
    response.status_code = 200 if mongo_ok else 503
    return {"status": "ok" if mongo_ok else "degraded", "checks": {"mongo": mongo_ok}}


# ── JSON API ─────────────────────────────────────────────────────────────────


@app.get("/api/campaigns")
async def api_campaigns() -> JSONResponse:
    """List campaigns observed in trace_events, newest activity first."""
    repo: TraceRepository = app.state.repo
    rows = await repo.list_campaigns(limit=settings.page_size)
    return JSONResponse(
        [
            {
                "campaign_id": r.campaign_id,
                "first_seen": r.first_seen.isoformat(),
                "last_seen": r.last_seen.isoformat(),
                "event_count": r.event_count,
                "services": r.services,
            }
            for r in rows
        ]
    )


@app.get("/api/campaigns/{campaign_id}/timeline")
async def api_timeline(campaign_id: str) -> JSONResponse:
    """Return the ordered trace event timeline for a campaign."""
    repo: TraceRepository = app.state.repo
    events = await repo.get_timeline(campaign_id)
    if not events:
        raise HTTPException(status_code=404, detail=f"No trace events for campaign {campaign_id!r}")
    return JSONResponse(
        [
            {
                "id": str(e.id),
                "trace_id": e.trace_id,
                "campaign_id": e.campaign_id,
                "service": e.service,
                "event_name": e.event_name,
                "phase": e.phase.value,
                "timestamp": e.timestamp.isoformat(),
                "duration_ms": e.duration_ms,
                "error_type": e.error_type,
                "error_message": e.error_message,
                "metadata": e.metadata,
            }
            for e in events
        ]
    )


# ── HTML pages ───────────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def page_campaigns(request: Request) -> HTMLResponse:
    repo: TraceRepository = app.state.repo
    rows = await repo.list_campaigns(limit=settings.page_size)
    return templates.TemplateResponse(
        request, "campaigns.html", {"campaigns": rows}
    )


@app.get("/campaigns/{campaign_id}", response_class=HTMLResponse)
async def page_timeline(request: Request, campaign_id: str) -> HTMLResponse:
    repo: TraceRepository = app.state.repo
    events = await repo.get_timeline(campaign_id)
    return templates.TemplateResponse(
        request,
        "timeline.html",
        {"campaign_id": campaign_id, "events": events},
    )


def run() -> None:
    uvicorn.run(
        "observability.main:app",
        host="0.0.0.0",
        port=settings.health_port,
        log_config=None,
    )


if __name__ == "__main__":
    run()
