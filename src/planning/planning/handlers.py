import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import structlog
from pymongo.errors import DuplicateKeyError

from local_infrastructure.factory.broker_interface import MessageBroker, NonRetryableError

from .config import settings
from .schemas import (
    KNOWN_SCORING_DIMENSIONS,
    LLMPlanOutput,
    LLMUsage,
    PlanReadyEvent,
    PlanRecord,
    PlanRequestedEvent,
    SourcingRequestedEvent,
)

log = structlog.get_logger(__name__)

LLMFn = Callable[[dict[str, Any], dict[str, Any]], Awaitable[tuple[LLMPlanOutput, LLMUsage]]]


def _warn_unknown_dimensions(weights: dict[str, float]) -> None:
    unknown = set(weights) - KNOWN_SCORING_DIMENSIONS
    if unknown:
        log.warning("plan uses non-standard scoring dimensions", dimensions=sorted(unknown))


async def handle_plan_requested(
    message: dict[str, Any],
    repo: Any,  # PlanRepository — typed Any to allow test doubles
    llm_fn: LLMFn,
    broker: MessageBroker,
) -> None:
    """Consume a plan.requested event end-to-end.

    Flow:
      1. Parse event.
      2. If a plan already exists for the campaign, republish plan.ready and exit.
      3. Load the campaign; if missing, raise NonRetryableError (goes to DLQ).
      4. Call the LLM, persist the plan, attach plan_id to campaign.
      5. Publish plan.ready.
    """
    event = PlanRequestedEvent.model_validate(message)
    logger = log.bind(campaign_id=event.campaign_id)
    logger.info("plan.requested received")

    existing = await repo.find_existing_plan_id(event.campaign_id)
    if existing is not None:
        logger.info("plan already exists, republishing plan.ready", plan_id=existing)
        await broker.publish(
            settings.plan_ready_queue,
            PlanReadyEvent(campaign_id=event.campaign_id, plan_id=existing).model_dump(),
        )
        await broker.publish(
            settings.sourcing_requested_queue,
            SourcingRequestedEvent(campaign_id=event.campaign_id, plan_id=existing).model_dump(),
        )
        return

    campaign = await repo.get_campaign(event.campaign_id)
    if campaign is None:
        raise NonRetryableError(f"campaign {event.campaign_id} not found")

    llm_out, usage = await llm_fn(campaign.icp, campaign.product_profile)
    _warn_unknown_dimensions(llm_out.scoring_weights)

    plan = PlanRecord(
        id=uuid4(),
        campaign_id=event.campaign_id,
        created_at=datetime.now(timezone.utc),
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
    await broker.publish(
        settings.plan_ready_queue,
        PlanReadyEvent(campaign_id=event.campaign_id, plan_id=plan_id_str).model_dump(),
    )
    await broker.publish(
        settings.sourcing_requested_queue,
        SourcingRequestedEvent(campaign_id=event.campaign_id, plan_id=plan_id_str).model_dump(),
    )
    logger.info("plan.ready and sourcing.requested published", plan_id=plan_id_str)


def _suppress_unused_logger_warning() -> None:  # pragma: no cover
    _ = logging.getLogger(__name__)
