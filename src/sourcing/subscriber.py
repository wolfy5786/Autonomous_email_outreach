"""RabbitMQ subscriber for sourcing.requested events."""
import asyncio
import json
import traceback
from typing import Any, Callable
from .config import config
from .pipeline import SourcingPipeline
from .publisher import publish_sourcing_completed, publish_sourcing_failed


async def handle_sourcing_requested(
    message: dict[str, Any],
    pipeline: SourcingPipeline,
    publish_fn: Callable,
) -> None:
    """Process a sourcing.requested event."""
    payload = message.get("payload", {})
    campaign_id = payload.get("campaignId", "unknown")
    retry_count = payload.get("retryCount", 0)

    try:
        result = await pipeline.run(campaign_id, payload)

        await publish_sourcing_completed(
            publish_fn,
            campaign_id=campaign_id,
            companies_found=result["qualified"],
        )

    except Exception as e:
        traceback.print_exc()
        await publish_sourcing_failed(
            publish_fn,
            campaign_id=campaign_id,
            error=str(e),
            retry_count=retry_count,
        )
