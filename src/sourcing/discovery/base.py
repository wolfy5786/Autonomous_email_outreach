"""
Discovery phase base types (Phase 1 — finding companies).

Concrete sources live in sibling modules; each returns raw candidate dicts,
not ``CompanyRecord`` instances.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from shared.models.plan import PlanRecord


@dataclass
class DiscoveryContext:
    """Inputs for a discovery run."""

    campaign_id: str
    plan: PlanRecord
    config: Any | None = None  # ``SourcingJobConfig`` from pipeline (avoid circular import)
    seeds: Any | None = None  # ``SourcingJobSeeds``


@dataclass
class DiscoveryResult:
    """Output of one discovery source."""

    source_name: str
    tier: str
    candidates: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class DiscoverySource(ABC):
    """
    One discoverable source from ``data_sourcing_map.md`` Phase 1.

    Tier ``A`` = structured directories; Tier ``B`` = signal/hint feeds requiring validation.
    """

    source_name: str
    tier: str  # "A" | "B"
    verticals: list[str]  # "SW" / "HC"; empty = applies to both

    @abstractmethod
    async def discover(self, ctx: DiscoveryContext) -> DiscoveryResult:
        """Enumerate candidate companies; implementations may raise ``NotImplementedError``."""
