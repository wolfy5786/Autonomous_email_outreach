from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Annotated, Literal

from beanie import Document
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pymongo import ASCENDING, IndexModel


def _created_at() -> datetime:
    return datetime.now(timezone.utc)


# --- LLM usage ---

class LLMUsage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


# --- Per-source filter models ---

class ProductHuntFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topics: list[str] | None = None
    posted_after: date | None = None
    posted_before: date | None = None
    min_votes: int | None = Field(default=None, ge=0)


class OpenCorporatesFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    jurisdiction_code: str | None = None
    company_type: str | None = None
    status: Literal["active", "dissolved", "inactive"] | None = None
    incorporation_date_from: date | None = None
    incorporation_date_to: date | None = None
    registered_address_country: str | None = None
    industry_keywords: list[str] | None = None


class YCNewsFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    batch_years: list[str] | None = None
    industries: list[str] | None = None
    company_stage: list[str] | None = None
    regions: list[str] | None = None


class YCDirectoryFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["Active", "Inactive", "Acquired"] | None = None
    batch_years: list[str] | None = None
    industries: list[str] | None = None
    subindustries: list[str] | None = None
    tags: list[str] | None = None
    regions: list[str] | None = None
    is_hiring: bool | None = None


class HackerNewsFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str | None = None
    tags: list[Literal["show_hn", "launch_hn", "story", "ask_hn"]] | None = None
    min_points: int | None = Field(default=None, ge=0)
    min_comments: int | None = Field(default=None, ge=0)
    created_after: date | None = None


# --- Source config wrappers (discriminated union by `source`) ---

class ProductHuntSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["product_hunt"]
    enabled: bool = True
    filters: ProductHuntFilters = Field(default_factory=ProductHuntFilters)


class OpenCorporatesSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["open_corporates"]
    enabled: bool = True
    filters: OpenCorporatesFilters = Field(default_factory=OpenCorporatesFilters)


class YCNewsSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["yc_news"]
    enabled: bool = True
    filters: YCNewsFilters = Field(default_factory=YCNewsFilters)


class YCDirectorySource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["yc_directory"]
    enabled: bool = True
    filters: YCDirectoryFilters = Field(default_factory=YCDirectoryFilters)


class HackerNewsSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["hacker_news"]
    enabled: bool = True
    filters: HackerNewsFilters = Field(default_factory=HackerNewsFilters)


SourceConfig = Annotated[
    ProductHuntSource
    | OpenCorporatesSource
    | YCNewsSource
    | YCDirectorySource
    | HackerNewsSource,
    Field(discriminator="source"),
]


# --- Global filters ---

class EmployeeCountRange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    min: int = Field(ge=0)
    max: int = Field(ge=0)

    @model_validator(mode="after")
    def _max_ge_min(self) -> "EmployeeCountRange":
        if self.max < self.min:
            raise ValueError("employee_count_range: max must be >= min")
        return self


class GlobalFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exclude_domains: list[str] | None = None
    employee_count_range: EmployeeCountRange | None = None
    languages: list[str] | None = None
    exclude_already_contacted: bool | None = None


# --- Outreach context ---

class OutreachContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    campaign_goal: str | None = None
    tone: str | None = None
    personalization_hints: list[str] | None = None
    sequence_length: int | None = Field(default=None, ge=1)


# --- Persisted plan (Beanie Document) ---

class PlanRecord(Document):
    """Planning Service output. Persisted by planning (`save_plan`) and read by sourcing.

    Schema mirrors `src/planning/planning/schemas.py:PlanRecord`. Mongo `_id` is the
    stringified plan UUID (see planning.repository.PlanRepository.save_plan).
    """

    model_config = ConfigDict(extra="ignore")

    id: str
    campaign_id: str
    sources: list[SourceConfig] = Field(default_factory=list)
    global_filters: GlobalFilters | None = None
    outreach_context: OutreachContext | None = None
    created_at: datetime = Field(default_factory=_created_at)
    llm_model: str | None = None
    llm_usage: LLMUsage | None = None

    class Settings:
        name = "plans"
        indexes = [
            IndexModel([("campaign_id", ASCENDING)], unique=True, name="uniq_campaign_id"),
            IndexModel([("id", ASCENDING)], unique=True, name="uniq_plan_id"),
        ]


# Alias for README naming
plan_record = PlanRecord
