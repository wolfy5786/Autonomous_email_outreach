"""Per-operation enrichment base types.

See ``design_docs/enrichment_redesign.md`` — enrichment is collapsed into three
fixed operations (LinkedIn POC, YC directory, company website). Each operation
takes an ``EnrichmentContext`` and emits a single ``OperationResult``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from shared.models.company import AttributeProvenance, CompanyRecord
from shared.models.plan import PlanRecord


@dataclass
class EnrichmentContext:
    """Per-company context handed to each enrichment operation."""

    campaign_id: str
    company: CompanyRecord
    plan: PlanRecord
    # Retained so ``sourcing.pipeline`` keeps compiling against this type; new
    # operations ignore it.
    missing_fields: list[str] = field(default_factory=list)


@dataclass
class OperationResult:
    """Output of a single enrichment operation.

    A dropped record (``dropped=True``) means the operation could not safely
    produce a usable slice for this company. Provenance is per-attribute so
    downstream personalization can cite the source for each field.
    """

    operation_name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, AttributeProvenance] = field(default_factory=dict)
    dropped: bool = False
    drop_reason: str | None = None
    errors: list[str] = field(default_factory=list)


class EnrichmentOperation(ABC):
    """Base class for the three fixed operations."""

    operation_name: str

    @abstractmethod
    async def run(self, ctx: EnrichmentContext) -> OperationResult: ...
