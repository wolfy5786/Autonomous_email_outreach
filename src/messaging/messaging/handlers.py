from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

import structlog

from local_infrastructure.factory.broker_interface import MessageBroker, NonRetryableError

from .config import Settings
from .credentials import CredentialsNotFoundError, CredentialsResolverProtocol
from .providers import EmailDraftProvider
from .repository import MessagingRepository
from .schemas import (
    DraftFailedEvent,
    DraftStatus,
    DraftWrittenEvent,
    LLMDraftOutput,
    LLMUsage,
    MessagingRequestedEvent,
)

log = structlog.get_logger(__name__)

LLMFn = Callable[..., Awaitable[tuple[LLMDraftOutput, LLMUsage]]]


async def handle_messaging_requested(
    message: dict[str, Any],
    *,
    repo: MessagingRepository,
    llm_fn: LLMFn,
    provider: EmailDraftProvider,
    credentials: CredentialsResolverProtocol,
    broker: MessageBroker,
    settings: Settings,
) -> None:
    """Consume one ``messaging.requested`` event end-to-end.

    Flow:
      1. Parse event.
      2. If a completed draft already exists (idempotent re-delivery):
         re-publish ``draft.written`` and return.
      3. Load context (email_account, plan, poc, company, hints) — missing
         data → ``NonRetryableError`` → DLQ.
      4. Resolve OAuth credentials — missing → ``NonRetryableError`` → DLQ.
      5. Upsert a generating-status draft row (idempotent on retry).
      6. Generate via LLM.
      7. Provider.create_draft (Gmail / stub).
      8. Mark draft_created and publish ``draft.written``.

    On failure in 6 or 7: ``mark_failed`` + publish ``draft.failed``; re-raise
    so the broker DLQ-routes the message (orchestrator decides whether to
    re-emit ``messaging.requested`` for a retry).
    """
    event = MessagingRequestedEvent.model_validate(message)
    logger = log.bind(campaign_id=event.campaign_id, poc_id=event.poc_id)
    if event.trace_id:
        logger = logger.bind(trace_id=event.trace_id)
    logger.info("messaging.requested received")

    # 2. Idempotency
    existing = await repo.find_existing_draft(event.campaign_id, event.poc_id)
    if existing is not None and existing.status is DraftStatus.DRAFT_CREATED:
        logger.info(
            "draft already exists, republishing draft.written",
            draft_id=existing.id,
            email_draft_ref=existing.email_draft_ref,
        )
        await broker.publish(
            settings.draft_written_queue,
            DraftWrittenEvent(
                campaign_id=event.campaign_id,
                draft_id=existing.id,
                poc_id=event.poc_id,
                email_draft_ref=existing.email_draft_ref or "",
            ).model_dump(),
        )
        return

    # 3. Load context — missing → DLQ
    email_account = await repo.get_campaign_email_account(event.campaign_id)
    if email_account is None:
        raise NonRetryableError(
            f"campaign {event.campaign_id} not found or missing config.email_account"
        )
    plan = await repo.get_plan_by_campaign(event.campaign_id)
    if plan is None:
        raise NonRetryableError(f"plan for campaign {event.campaign_id} not found")
    poc = await repo.get_poc(event.poc_id)
    if poc is None:
        raise NonRetryableError(f"poc {event.poc_id} not found")
    company = await repo.get_company(poc.company_id)
    if company is None:
        raise NonRetryableError(f"company {poc.company_id} not found")
    hints = await repo.top_hints(company.id, event.campaign_id, limit=5)
    logger.info("context loaded", company=company.domain, hints_count=len(hints))

    # 4. Credentials
    try:
        oauth = credentials.resolve(email_account.credentials_ref)
    except CredentialsNotFoundError as e:
        raise NonRetryableError(str(e)) from e

    # 5. Upsert generating row
    draft_id, retry_count = await repo.upsert_generating_draft(
        new_draft_id=str(uuid4()),
        campaign_id=event.campaign_id,
        company_id=company.id,
        poc_id=event.poc_id,
    )
    logger = logger.bind(draft_id=draft_id, attempt=retry_count + 1)
    logger.info("draft attempt starting")

    # 6 + 7. LLM + provider
    try:
        llm_out, usage = await llm_fn(plan=plan, company=company, poc=poc, hints=hints)
        logger.info("llm completed", total_tokens=usage.total_tokens)
        created = await provider.create_draft(
            to=poc.email,
            subject=llm_out.subject,
            body=llm_out.body,
            oauth_credentials=oauth,
        )
        logger.info(
            "provider draft created",
            provider=created.provider.value,
            email_draft_ref=created.provider_draft_id,
        )
    except Exception as e:
        err_str = f"{type(e).__name__}: {e}"
        logger.error("draft generation failed", error=err_str)
        await repo.mark_failed(draft_id, error=err_str)
        await broker.publish(
            settings.draft_failed_queue,
            DraftFailedEvent(
                campaign_id=event.campaign_id,
                draft_id=draft_id,
                poc_id=event.poc_id,
                error=err_str,
                retry_count=retry_count,
            ).model_dump(),
        )
        raise  # broker DLQs

    # 8. Persist + publish success
    await repo.mark_draft_created(
        draft_id,
        subject=llm_out.subject,
        body=llm_out.body,
        hooks=llm_out.personalization_hooks,
        provider=created.provider,
        email_draft_ref=created.provider_draft_id,
        llm_model=settings.llm_model,
        llm_usage=usage,
    )
    await broker.publish(
        settings.draft_written_queue,
        DraftWrittenEvent(
            campaign_id=event.campaign_id,
            draft_id=draft_id,
            poc_id=event.poc_id,
            email_draft_ref=created.provider_draft_id,
        ).model_dump(),
    )
    logger.info("draft.written published")
