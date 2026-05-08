"""Prospect data model shared across services."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ProspectStatus(str, Enum):
    DISCOVERED = "discovered"
    ENRICHED = "enriched"
    QUALIFIED = "qualified"
    CONTACTED = "contacted"
    REPLIED = "replied"
    BOUNCED = "bounced"


@dataclass
class Prospect:
    id: str
    campaign_id: str
    company_id: str
    first_name: str
    last_name: str
    email: str
    title: str
    company_name: str
    status: ProspectStatus = ProspectStatus.DISCOVERED
    icp_score: float = 0.0
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None
    metadata: dict = field(default_factory=dict)
