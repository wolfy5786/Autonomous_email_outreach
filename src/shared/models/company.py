from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from beanie import Document, Indexed
from pydantic import BaseModel, ConfigDict, Field
from pymongo import ASCENDING, IndexModel

from shared.models.enums import FundingStage, ScrapeMode, SourceType


class Headquarters(BaseModel):
    """Company HQ location (README core field)."""

    model_config = ConfigDict(frozen=True)

    city: str | None = None
    country: str | None = None


class AttributeProvenance(BaseModel):
    """
    Option A sidecar: metadata for a single core or ``extra`` attribute
    (see ``docs/data-sourcing-service.md`` §9.1).
    """

    model_config = ConfigDict(frozen=True)

    source_name: str
    source_type: SourceType
    observed_value: Any | None = None
    normalized_value: Any | None = None
    confidence: float
    evidence_urls: list[str] = Field(default_factory=list)
    snippet: str | None = None
    extracted_at: datetime


class CompanyRecord(Document):
    """
    Enforced + semi-structured company document (``README`` company_record, collection ``companies``).
    """

    # UUID string as Mongo _id (README: id: string (uuid))
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    name: str
    domain: Annotated[str, Indexed(unique=True)]
    industry: str | None = None
    employee_count: int | None = None
    headquarters: Headquarters | None = None
    funding_stage: FundingStage = FundingStage.UNKNOWN
    tech_stack: list[str] = Field(default_factory=list)
    description: str | None = None
    linkedin_url: str | None = None
    website_url: str | None = None
    icp_fit_score: float | None = None
    data_completeness: float = 0.0
    freshness_timestamp: datetime
    scrape_mode_last: ScrapeMode = ScrapeMode.ALL
    campaign_ids: list[str] = Field(default_factory=list)
    enriched: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)

    # Option A: sidecar map keyed by attribute name (core or extra key)
    provenance: dict[str, AttributeProvenance] = Field(default_factory=dict)

    class Settings:
        name = "companies"
        indexes = [
            IndexModel([("campaign_ids", ASCENDING)]),
            IndexModel([("freshness_timestamp", ASCENDING)]),
        ]


# Backwards-friendly alias
company_record = CompanyRecord
