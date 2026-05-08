"""Email draft data model."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime


class DraftStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    SENT = "sent"
    FAILED = "failed"
    RETRY = "retry"
    BOUNCED = "bounced"


@dataclass
class EmailDraft:
    id: str
    campaign_id: str
    prospect_id: str
    subject: str
    body: str
    status: DraftStatus = DraftStatus.PENDING
    retry_count: int = 0
    sent_at: Optional[datetime] = None
    opened: bool = False
    replied: bool = False
    metadata: dict = field(default_factory=dict)
