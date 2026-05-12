from __future__ import annotations

import uuid
from datetime import datetime, timezone

from beanie import Document
from pydantic import BaseModel, ConfigDict, Field
from pymongo import ASCENDING, IndexModel

from shared.models.enums import DraftStatus, EmailProvider


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LLMUsage(BaseModel):
    """LLM token accounting (mirrors planning.LLMUsage)."""

    model_config = ConfigDict(extra="ignore")
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class EmailDraft(Document):
    """Persisted email draft (README ``email_draft_record``, collection ``email_drafts``)."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campaign_id: str
    company_id: str
    poc_id: str
    subject: str = ""
    body: str = ""
    personalization_hooks: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=_utcnow)
    status: DraftStatus = DraftStatus.GENERATING
    email_draft_ref: str | None = None
    email_provider: EmailProvider | None = None
    error: str | None = None
    retry_count: int = 0
    llm_model: str | None = None
    llm_usage: LLMUsage | None = None

    class Settings:
        name = "email_drafts"
        indexes = [
            IndexModel(
                [("campaign_id", ASCENDING), ("poc_id", ASCENDING)],
                unique=True,
                name="uniq_campaign_poc",
            ),
            IndexModel(
                [("campaign_id", ASCENDING), ("status", ASCENDING)],
                name="campaign_status",
            ),
        ]


email_draft_record = EmailDraft  # README naming alias
