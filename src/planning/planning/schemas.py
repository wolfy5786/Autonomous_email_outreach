from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Fixed tone taxonomy. Messaging service relies on this — if you loosen it,
# coordinate with messaging's tone-handling code.
EmailTone = Literal[
    "consultative",
    "direct",
    "technical",
    "peer-to-peer",
    "warm",
    "executive-brief",
]

# Recommended scoring dimension keys. The LLM is instructed to use these, and the
# Prospecting service relies on predictable keys. Unknown keys are allowed (soft
# validation via a log warning) so the LLM can add campaign-specific dimensions.
KNOWN_SCORING_DIMENSIONS = frozenset(
    {
        "industry_match",
        "size_match",
        "tech_stack_match",
        "funding_stage_match",
        "geography_match",
        "seniority_match",
        "title_match",
        "department_match",
    }
)


class PlanRequestedEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    campaign_id: str


class PlanReadyEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    campaign_id: str
    plan_id: str


class CampaignRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    icp: dict[str, Any]
    product_profile: dict[str, Any]
    plan_id: str | None = None


class LLMUsage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMPlanOutput(BaseModel):
    """Exactly what we ask the LLM to return — validated before persisting."""

    model_config = ConfigDict(extra="forbid")

    company_signals: list[str] = Field(min_length=3, max_length=20)
    poc_signals: list[str] = Field(min_length=3, max_length=15)
    scoring_weights: dict[str, float] = Field(min_length=1)
    personalization_hooks: list[str] = Field(min_length=3, max_length=15)
    email_tone: EmailTone
    email_angle: str = Field(min_length=10, max_length=400)

    @model_validator(mode="after")
    def _weights_sum_to_one(self) -> "LLMPlanOutput":
        total = sum(self.scoring_weights.values())
        if abs(total - 1.0) > 0.05:
            raise ValueError(f"scoring_weights must sum to 1.0 (+/-0.05), got {total:.3f}")
        for v in self.scoring_weights.values():
            if v < 0:
                raise ValueError("scoring_weights values must be non-negative")
        return self


class PlanRecord(LLMPlanOutput):
    """Persisted plan document. Mongo `_id` is set to the stringified `id`."""

    model_config = ConfigDict(extra="ignore")

    id: UUID
    campaign_id: str
    created_at: datetime
    llm_model: str
    llm_usage: LLMUsage | None = None
