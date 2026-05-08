"""Company data model."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Company:
    id: str
    name: str
    domain: str
    industry: str
    size: str
    region: str
    description: Optional[str] = None
    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    funding_stage: Optional[str] = None
    metadata: dict = field(default_factory=dict)
