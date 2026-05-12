import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

import structlog
from pymongo.errors import DuplicateKeyError

from .config import settings
from .schemas import (
    LLMPlanOutput,
    LLMUsage,
    PlanReadyEvent,
    PlanRecord,
    PlanRequestedEvent,
    SourcingRequestedEvent,
)

log = structlog.get_logger(__name__)

LLMFn = Callable[[dict[str, Any], dict[str, Any]], Awaitable[tuple[LLMPlanOutput, LLMUsage]]]


class NonRetryableError(Exception):
    """Permanent failure — message must not be requeued (routes to DLQ via x-dead-letter)."""


class EventPublisher(Protocol):
    async def publish(self, routing_key: str, message: dict[str, Any]) -> None: ...


async def _publish_plan_ready_and_sourcing(
    publisher: EventPublisher,
    campaign_id: str,
    plan_id: str,
) -> None:
    await publisher.publish(
        settings.plan_ready_queue,
        PlanReadyEvent(campaign_id=campaign_id, plan_id=plan_id).model_dump(),
    )
    await publisher.publish(
        settings.sourcing_requested_queue,
        SourcingRequestedEvent(campaign_id=campaign_id, plan_id=plan_id).model_dump(),
    )


async def handle_plan_requested(
    message: dict[str, Any],
    repo: Any,  # PlanRepository — typed Any to allow test doubles
    llm_fn: LLMFn,
    publisher: EventPublisher,
) -> None:
    """Consume a plan.requested event end-to-end.

    Flow:
      1. Parse event.
      2. If a plan already exists for the campaign, republish plan.ready + sourcing.requested and exit.
      3. Load the campaign; if missing, raise NonRetryableError (goes to DLQ).
      4. Call the LLM, persist the plan, attach plan_id to campaign.
      5. Publish plan.ready and sourcing.requested (same routing keys as definitions.json).
    """
    event = PlanRequestedEvent.model_validate(message)
    logger = log.bind(campaign_id=event.campaign_id)
    logger.info("plan.requested received")

    existing = await repo.find_existing_plan_id(event.campaign_id)
    if existing is not None:
        logger.info("plan already exists, republishing plan.ready + sourcing.requested", plan_id=existing)
        await _publish_plan_ready_and_sourcing(publisher, event.campaign_id, existing)
        return

    campaign = await repo.get_campaign(event.campaign_id)
    if campaign is None:
        raise NonRetryableError(f"campaign {event.campaign_id} not found")

    llm_out, usage = await llm_fn(campaign.icp, campaign.product_profile)

    plan = PlanRecord(
        id=uuid4(),
        campaign_id=event.campaign_id,
        created_at=datetime.now(UTC),
        llm_model=settings.llm_model,
        llm_usage=usage,
        **llm_out.model_dump(),
    )

    try:
        await repo.save_plan(plan)
        plan_id_str = str(plan.id)
    except DuplicateKeyError:
        # Another worker finished first — find the winning id and publish it.
        existing = await repo.find_existing_plan_id(event.campaign_id)
        if existing is None:
            raise NonRetryableError("duplicate key on save_plan but no existing plan found") from None
        plan_id_str = existing
        logger.info("duplicate plan on insert — using existing", plan_id=plan_id_str)

    # Validate the id is a well-formed UUID string before publishing.
    UUID(plan_id_str)

    await repo.attach_plan_to_campaign(event.campaign_id, plan_id_str)
    await _publish_plan_ready_and_sourcing(publisher, event.campaign_id, plan_id_str)
    logger.info("plan.ready and sourcing.requested published", plan_id=plan_id_str)


def _suppress_unused_logger_warning() -> None:  # pragma: no cover
    _ = logging.getLogger(__name__)
