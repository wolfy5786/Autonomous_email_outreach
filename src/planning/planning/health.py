from typing import Any

from fastapi import APIRouter, Response

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: process is up."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(response: Response, deps: dict[str, Any] | None = None) -> dict[str, Any]:
    """Readiness: stubbed — see main.py where the route is rebound with live deps."""
    response.status_code = 200
    return {"status": "ok", "checks": {}}
