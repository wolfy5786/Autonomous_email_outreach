"""
Enrichment validation — schema, evidence, conflicts after Phase 2 sources run.

Aligns with ``docs/data-sourcing-service.md`` §8.2.
"""

from __future__ import annotations

from typing import Any

from source_map import AttributeSourceMapRule


def validate_enrichment(result: Any, rule: AttributeSourceMapRule) -> bool:
    """
    Validate a single enrichment result against its attribute map rule.

    When implemented, this gate should:

    - **Schema validation** — parsed output matches ``rule.extraction_schema`` (JSON Schema).
    - **Evidence** — required fields from web/SERP must include at least one ``source_url``
      in provenance (see ``AttributeProvenance.evidence_urls``).
    - **Freshness** — compare ``extracted_at`` / content hash vs campaign ``freshness_days``.
    - **Conflict resolution** — when sources disagree, use ``confidence_weight`` and ``priority``;
      if still ambiguous, keep alternates under ``extra`` with lower confidence (per spec §9.1).

    :param result: Typically ``EnrichmentResult`` from ``enrichment.base`` (kept as ``Any`` to avoid import cycles).
    :param rule: The ``AttributeSourceMapRule`` that produced this attempt.
    :returns: ``True`` if the enrichment passes all gates; ``False`` to discard or downgrade.

    :raises NotImplementedError: Stub until validators are wired.
    """
    raise NotImplementedError(
        "validate_enrichment: implement schema check, evidence URLs for web fields, "
        "freshness, and conflict handling using rule.confidence_weight / priority."
    )
