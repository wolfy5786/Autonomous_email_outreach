from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel

from shared.models.enums import HintCategory, SourceType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Hint(Document):
    """
    Personalization signal for a company in a campaign: why they might care, with evidence.
    Used by prospecting and messaging; sourced during discovery or enrichment.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    campaign_id: str
    category: HintCategory
    summary: str
    source_name: str
    source_type: SourceType
    source_url: str | None = None
    raw_snippet: str | None = None
    relevance_score: float | None = None
    discovered_at: datetime = Field(default_factory=_utcnow)
    extra: dict[str, Any] = Field(default_factory=dict)

    class Settings:
        name = "hints"
        indexes = [
            IndexModel([("company_id", ASCENDING)]),
            IndexModel([("campaign_id", ASCENDING)]),
            IndexModel([("company_id", ASCENDING), ("campaign_id", ASCENDING)]),
            IndexModel([("category", ASCENDING)]),
        ]


# Alias for readability
hint_record = Hint
