"""
Enrichment phase base types (Phase 2 — deepening known companies).

Concrete sources fill attributes + provenance; no persistence here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from shared.models.company import AttributeProvenance, CompanyRecord
from shared.models.plan import PlanRecord


@dataclass
class EnrichmentContext:
    """One company + plan context for enrichment."""

    campaign_id: str
    company: CompanyRecord
    plan: PlanRecord
    missing_fields: list[str] = field(default_factory=list)


@dataclass
class EnrichmentResult:
    """Structured output from one enrichment source."""

    source_name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, AttributeProvenance] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class EnrichmentSource(ABC):
    """Maps to ``source_name`` in ``AttributeSourceMapRule``."""

    source_name: str

    @abstractmethod
    async def enrich(self, ctx: EnrichmentContext) -> EnrichmentResult:
        """Fill attributes for ``ctx.company``; may raise ``NotImplementedError``."""
