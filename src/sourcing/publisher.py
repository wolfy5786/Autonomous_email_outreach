"""Publish sourcing stage events back to the orchestrator."""
import json
from datetime import datetime, timezone
from typing import Any, Callable


async def publish_sourcing_completed(
    publish_fn: Callable,
    campaign_id: str,
    companies_found: int,
) -> None:
    """Notify orchestrator that sourcing is done."""
    await publish_fn(
        routing_key="sourcing.completed",
        payload={
            "type": "sourcing.completed",
            "campaignId": campaign_id,
            "companiesFound": companies_found,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


async def publish_sourcing_failed(
    publish_fn: Callable,
    campaign_id: str,
    error: str,
    retry_count: int,
) -> None:
    """Notify orchestrator that sourcing failed."""
    await publish_fn(
        routing_key="sourcing.failed",
        payload={
            "type": "sourcing.failed",
            "campaignId": campaign_id,
            "error": error,
            "retryCount": retry_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
