from __future__ import annotations

import uuid
from datetime import datetime, timezone

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel


def _created_at() -> datetime:
    return datetime.now(timezone.utc)


class PlanRecord(Document):
    """
    Planning Service output: ICP→mining plan, scoring weights, tone, hooks
    (``README`` ``plan_record``, collection ``plans``).
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campaign_id: str
    company_signals: list[str] = Field(default_factory=list)
    poc_signals: list[str] = Field(default_factory=list)
    scoring_weights: dict[str, float] = Field(default_factory=dict)
    personalization_hooks: list[str] = Field(default_factory=list)
    email_tone: str
    email_angle: str
    created_at: datetime = Field(default_factory=_created_at)

    class Settings:
        name = "plans"
        indexes = [
            IndexModel([("campaign_id", ASCENDING)]),
        ]


# Alias for README naming
plan_record = PlanRecord
