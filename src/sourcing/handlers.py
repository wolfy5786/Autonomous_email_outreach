"""Top-level message handlers for the sourcing service."""
import asyncio
import traceback
from typing import Any
from .pipeline import SourcingPipeline
from .publisher import publish_sourcing_completed, publish_sourcing_failed
from .logging_setup import subscriber_logger as logger


class SourcingHandler:
    """Handle inbound RabbitMQ messages for sourcing."""

    def __init__(self) -> None:
        self._pipeline = SourcingPipeline()

    async def on_sourcing_requested(
        self,
        message: dict[str, Any],
        publish_fn: Any,
    ) -> None:
        payload = message.get("payload", {})
        campaign_id = payload.get("campaignId", "unknown")
        retry_count = payload.get("retryCount", 0)

        logger.info(
            f"Processing sourcing.requested for campaign {campaign_id} "
            f"(attempt {retry_count + 1})"
        )

        try:
            result = await self._pipeline.run(campaign_id, payload)

            logger.info(
                f"Sourcing complete for {campaign_id}: "
                f"{result['qualified']} qualified companies"
            )

            await publish_sourcing_completed(
                publish_fn,
                campaign_id=campaign_id,
                companies_found=result["qualified"],
            )

        except Exception as e:
            logger.error(f"Sourcing failed for {campaign_id}: {e}")
            traceback.print_exc()
            await publish_sourcing_failed(
                publish_fn,
                campaign_id=campaign_id,
                error=str(e),
                retry_count=retry_count,
            )
