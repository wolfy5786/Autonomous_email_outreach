import logging
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from shared.models import EmailDraft

from .schemas import (
    CompanyContext,
    DraftStatus,
    EmailAccountConfig,
    EmailProvider,
    HintContext,
    LLMUsage,
    PlanContext,
    PocRecord,
)

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MessagingRepository:
    """Mongo access for the Messaging service.

    Convention (matches planning/repository.py): business `id` is stored as
    Mongo `_id`. Idempotency on `email_drafts` relies on the
    `(campaign_id, poc_id)` unique index, which is created by `init_beanie`
    at service startup.
    """

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._db = db

    @classmethod
    def from_url(cls, mongo_url: str, db_name: str) -> "MessagingRepository":
        client: AsyncIOMotorClient[dict[str, Any]] = AsyncIOMotorClient(mongo_url)
        return cls(client[db_name])

    @property
    def db(self) -> AsyncIOMotorDatabase:
        return self._db

    async def ping(self) -> bool:
        try:
            await self._db.command("ping")
            return True
        except Exception:
            log.exception("mongo ping failed")
            return False

    # ── Reads ──────────────────────────────────────────────────

    async def get_campaign_email_account(self, campaign_id: str) -> EmailAccountConfig | None:
        doc = await self._db["campaigns"].find_one({"campaign_id": campaign_id})
        if doc is None:
            doc = await self._db["campaigns"].find_one({"_id": campaign_id})
        if doc is None:
            doc = await self._db["campaigns"].find_one({"id": campaign_id})
        if doc is None:
            return None
        ea = (doc.get("config") or {}).get("email_account")
        if not ea:
            return None
        return EmailAccountConfig.model_validate(ea)

    async def get_poc(self, poc_id: str) -> PocRecord | None:
        doc = await self._db["persons"].find_one({"_id": poc_id})
        if doc is None:
            doc = await self._db["persons"].find_one({"id": poc_id})
        if doc is None:
            return None
        if "id" not in doc and "_id" in doc:
            doc["id"] = doc["_id"]
        return PocRecord.model_validate(doc)

    async def get_company(self, company_id: str) -> CompanyContext | None:
        doc = await self._db["companies"].find_one({"_id": company_id})
        if doc is None:
            doc = await self._db["companies"].find_one({"id": company_id})
        if doc is None:
            return None
        if "id" not in doc and "_id" in doc:
            doc["id"] = doc["_id"]
        return CompanyContext.model_validate(doc)

    async def get_plan_by_campaign(self, campaign_id: str) -> PlanContext | None:
        doc = await self._db["plans"].find_one({"campaign_id": campaign_id})
        if doc is None:
            return None
        if "id" not in doc and "_id" in doc:
            doc["id"] = doc["_id"]
        return PlanContext.model_validate(doc)

    async def top_hints(
        self, company_id: str, campaign_id: str, limit: int = 5
    ) -> list[HintContext]:
        cursor = (
            self._db["hints"]
            .find({"company_id": company_id, "campaign_id": campaign_id})
            .sort("relevance_score", -1)
            .limit(limit)
        )
        return [HintContext.model_validate(doc) async for doc in cursor]

    async def find_existing_draft(
        self, campaign_id: str, poc_id: str
    ) -> EmailDraft | None:
        doc = await self._db["email_drafts"].find_one(
            {"campaign_id": campaign_id, "poc_id": poc_id}
        )
        if doc is None:
            return None
        if "id" not in doc and "_id" in doc:
            doc["id"] = doc["_id"]
        return EmailDraft.model_validate(doc)

    # ── Writes ─────────────────────────────────────────────────

    async def upsert_generating_draft(
        self,
        *,
        new_draft_id: str,
        campaign_id: str,
        company_id: str,
        poc_id: str,
    ) -> tuple[str, int]:
        """Idempotent. Returns ``(draft_id, retry_count)``.

        - No existing row → insert with id=new_draft_id, retry_count=0.
        - Existing row (status=generating|failed) → bump retry_count, set
          status=generating, reuse the existing draft_id.
        - Caller MUST short-circuit when status=draft_created BEFORE calling
          this method; this method is only for active attempts.
        """
        existing = await self._db["email_drafts"].find_one(
            {"campaign_id": campaign_id, "poc_id": poc_id}
        )
        if existing is None:
            doc = _new_generating_draft_doc(
                draft_id=new_draft_id,
                campaign_id=campaign_id,
                company_id=company_id,
                poc_id=poc_id,
            )
            await self._db["email_drafts"].insert_one(doc)
            return new_draft_id, 0

        new_retry = int(existing.get("retry_count", 0)) + 1
        await self._db["email_drafts"].update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "status": DraftStatus.GENERATING.value,
                    "retry_count": new_retry,
                    "error": None,
                    "generated_at": _utcnow().isoformat(),
                }
            },
        )
        existing_id = existing.get("id") or existing.get("_id")
        return str(existing_id), new_retry

    async def mark_failed(self, draft_id: str, *, error: str) -> None:
        await self._db["email_drafts"].update_one(
            {"_id": draft_id},
            {"$set": {"status": DraftStatus.FAILED.value, "error": error}},
        )

    async def mark_draft_created(
        self,
        draft_id: str,
        *,
        subject: str,
        body: str,
        hooks: list[str],
        provider: EmailProvider,
        email_draft_ref: str,
        llm_model: str | None = None,
        llm_usage: LLMUsage | None = None,
    ) -> None:
        update: dict[str, Any] = {
            "status": DraftStatus.DRAFT_CREATED.value,
            "subject": subject,
            "body": body,
            "personalization_hooks": hooks,
            "email_provider": provider.value,
            "email_draft_ref": email_draft_ref,
            "error": None,
        }
        if llm_model is not None:
            update["llm_model"] = llm_model
        if llm_usage is not None:
            update["llm_usage"] = llm_usage.model_dump()
        await self._db["email_drafts"].update_one({"_id": draft_id}, {"$set": update})


def _new_generating_draft_doc(
    *, draft_id: str, campaign_id: str, company_id: str, poc_id: str
) -> dict[str, Any]:
    """Build a fresh email_drafts document.

    Bypasses Beanie's ``__init__`` (which would require ``init_beanie`` to have
    been called) so the repository works identically in unit tests and in
    production. Field set must stay in sync with ``shared.models.EmailDraft``.
    """
    return {
        "_id": draft_id,
        "id": draft_id,
        "campaign_id": campaign_id,
        "company_id": company_id,
        "poc_id": poc_id,
        "subject": "",
        "body": "",
        "personalization_hooks": [],
        "generated_at": _utcnow().isoformat(),
        "status": DraftStatus.GENERATING.value,
        "email_draft_ref": None,
        "email_provider": None,
        "error": None,
        "retry_count": 0,
        "llm_model": None,
        "llm_usage": None,
    }
