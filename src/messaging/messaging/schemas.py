from pydantic import BaseModel, ConfigDict, Field, field_validator

# Re-exported so messaging code can `from messaging.schemas import LLMUsage`
# without reaching into shared.models for a type that's used everywhere here.
from shared.models import DraftStatus, EmailProvider, LLMUsage

__all__ = (
    "CompanyContext",
    "DraftFailedEvent",
    "DraftStatus",
    "DraftWrittenEvent",
    "EmailAccountConfig",
    "EmailProvider",
    "HintContext",
    "LLMDraftOutput",
    "LLMUsage",
    "MessagingRequestedEvent",
    "PlanContext",
    "PocRecord",
)


# ── Inbound event ───────────────────────────────────────────────

class MessagingRequestedEvent(BaseModel):
    """`messaging.requested` payload — README §Message Queues."""

    model_config = ConfigDict(extra="ignore")
    campaign_id: str
    poc_id: str
    trace_id: str | None = None


# ── Outbound events ─────────────────────────────────────────────

class DraftWrittenEvent(BaseModel):
    """`draft.written` payload — README §Message Queues."""

    model_config = ConfigDict(extra="ignore")
    campaign_id: str
    draft_id: str
    poc_id: str
    email_draft_ref: str


class DraftFailedEvent(BaseModel):
    """`draft.failed` payload — README §Message Queues."""

    model_config = ConfigDict(extra="ignore")
    campaign_id: str
    draft_id: str
    poc_id: str
    error: str
    retry_count: int = 0


# ── LLM contract ────────────────────────────────────────────────

class LLMDraftOutput(BaseModel):
    """Exactly what we ask the LLM to return — validated before persisting."""

    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=5, max_length=120)
    body: str = Field(min_length=50, max_length=3000)
    personalization_hooks: list[str] = Field(min_length=1, max_length=10)


# ── Defensive read models ───────────────────────────────────────
# Prospecting hasn't shipped yet (see plan). The repository reads `persons`
# docs as raw dicts and adapts them through this model so missing/extra keys
# don't crash messaging. Once Prospecting lands a canonical Person model in
# shared.models, swap this for a thin alias or delete it outright.

class PocRecord(BaseModel):
    """Defensive POC adapter — ignores unknown fields."""

    model_config = ConfigDict(extra="ignore")

    id: str
    company_id: str
    first_name: str | None = None
    last_name: str | None = None
    title: str | None = None
    seniority: str | None = None
    department: str | None = None
    email: str
    email_verified: bool = False
    icp_poc_score: float | None = None

    @field_validator("id", "company_id")
    @classmethod
    def _no_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must be non-empty")
        return v


class CompanyContext(BaseModel):
    """Lean projection of CompanyRecord that messaging actually needs."""

    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    domain: str
    industry: str | None = None
    description: str | None = None


class PlanContext(BaseModel):
    """Lean projection of PlanRecord that messaging actually needs."""

    model_config = ConfigDict(extra="ignore")

    id: str
    campaign_id: str
    email_tone: str
    email_angle: str
    personalization_hooks: list[str] = Field(default_factory=list)


class HintContext(BaseModel):
    """Lean projection of Hint that messaging passes to the LLM."""

    model_config = ConfigDict(extra="ignore")

    category: str
    summary: str
    source_url: str | None = None
    relevance_score: float | None = None


class EmailAccountConfig(BaseModel):
    """`campaign.config.email_account` — README §Data Schema."""

    model_config = ConfigDict(extra="ignore")

    provider: EmailProvider
    credentials_ref: str
