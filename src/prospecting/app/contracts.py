from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ProspectingEventBase(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)


class ProspectingDocumentBase(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True, str_strip_whitespace=True)


class SourcingCompletedEvent(ProspectingEventBase):
    campaign_id: str
    entity_ids: list[str] = Field(default_factory=list)


class RankedProspect(ProspectingEventBase):
    company_id: str
    poc_id: str
    score: float = Field(ge=0.0, le=1.0)


class ProspectingCompletedEvent(ProspectingEventBase):
    campaign_id: str
    ranked_prospects: list[RankedProspect] = Field(default_factory=list)


class CampaignDocument(ProspectingDocumentBase):
    id: str = Field(validation_alias=AliasChoices("id", "_id"))
    name: str | None = None
    status: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class PlanDocument(ProspectingDocumentBase):
    id: str = Field(validation_alias=AliasChoices("id", "_id"))
    campaign_id: str
    scoring_weights: dict[str, float] = Field(default_factory=dict)


class CompanyDocument(ProspectingDocumentBase):
    id: str = Field(validation_alias=AliasChoices("id", "_id"))
    name: str | None = None
    domain: str | None = None
    industry: str | None = None
    employee_count: int | None = Field(default=None, validation_alias=AliasChoices("employee_count", "employees"))
    description: str | None = None
    linkedin_url: str | None = None
    website_url: str | None = None
    icp_fit_score: float | None = None


class PersonDocument(ProspectingDocumentBase):
    id: str = Field(validation_alias=AliasChoices("id", "_id"))
    company_id: str
    name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    title: str | None = None
    seniority: str | None = None
    department: str | None = None
    email: str | None = None
    email_verified: bool = False
    linkedin_url: str | None = None
    icp_poc_score: float | None = None
