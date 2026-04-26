"""Queue contracts for sourcing service messages."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourcingRequestedEvent:
    campaign_id: str
    plan_id: str
    target_entities: list[dict[str, Any]] = field(default_factory=list)
    request_id: str | None = None
    config: dict[str, Any] = field(default_factory=dict)
    seeds: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "SourcingRequestedEvent":
        return cls(
            campaign_id=str(payload.get("campaign_id", "")),
            plan_id=str(payload.get("plan_id", "")),
            target_entities=list(payload.get("target_entities", [])),
            request_id=payload.get("request_id"),
            config=dict(payload.get("config", {})),
            seeds=dict(payload.get("seeds", {})),
        )


@dataclass(frozen=True)
class SourcingCompletedEvent:
    campaign_id: str
    entity_ids: list[str]
    stats: dict[str, int] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "entity_ids": self.entity_ids,
            "stats": self.stats,
        }


@dataclass(frozen=True)
class SourcingPartialEvent:
    campaign_id: str
    entity_id: str
    missing_fields: list[str]
    failure_code: str = "data_incomplete"

    def to_payload(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "entity_id": self.entity_id,
            "missing_fields": self.missing_fields,
            "failure_code": self.failure_code,
        }

