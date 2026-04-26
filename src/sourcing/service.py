"""Sourcing service orchestration layer."""

import logging

from .config import SourcingConfig
from .contracts import SourcingCompletedEvent, SourcingPartialEvent, SourcingRequestedEvent
from .messaging.broker_interface import MessageBroker
from .pipeline import SourcingPipeline


class SourcingService:
    def __init__(
        self,
        config: SourcingConfig,
        broker: MessageBroker,
        pipeline: SourcingPipeline,
        logger: logging.LoggerAdapter,
    ):
        self.config = config
        self.broker = broker
        self.pipeline = pipeline
        self.logger = logger

    async def start(self) -> None:
        self.logger.info(
            "service=sourcing action=start broker_type=%s subscribe_topic=%s",
            self.config.broker_type,
            self.config.sourcing_requested_topic,
        )
        await self.broker.subscribe(self.config.sourcing_requested_topic, self._on_sourcing_requested)

    async def stop(self) -> None:
        self.logger.info("service=sourcing action=stop")
        await self.broker.disconnect()

    async def _on_sourcing_requested(self, payload: dict) -> None:
        event = SourcingRequestedEvent.from_payload(payload)
        request_logger = logging.LoggerAdapter(
            self.logger.logger,
            {"request_id": event.request_id or "-", "campaign_id": event.campaign_id},
        )
        request_logger.info("event=sourcing.requested status=received")

        result = await self.pipeline.run(event)

        completed = SourcingCompletedEvent(
            campaign_id=event.campaign_id,
            entity_ids=result.discovered_entity_ids,
            stats=result.stats,
        )
        await self.broker.publish(self.config.sourcing_completed_topic, completed.to_payload())
        request_logger.info(
            "event=sourcing.completed status=published entity_count=%d",
            len(result.discovered_entity_ids),
        )

        for entity_id, missing_fields in result.partial_entity_gaps.items():
            partial = SourcingPartialEvent(
                campaign_id=event.campaign_id,
                entity_id=entity_id,
                missing_fields=missing_fields,
            )
            await self.broker.publish(self.config.sourcing_partial_topic, partial.to_payload())
            request_logger.info(
                "event=sourcing.partial status=published entity_id=%s missing_fields=%d",
                entity_id,
                len(missing_fields),
            )

