"""Three fixed enrichment operations (see ``design_docs/enrichment_redesign.md``).

Each operation produces one independent slice of evidence per company and can
be run in parallel with the others. ``ENRICHMENT_BY_SOURCE_NAME`` is kept as
an empty dict for back-compat with ``sourcing.pipeline`` while it still
iterates ``AttributeSourceMapRule`` entries — the broader rewire from the
per-attribute source map to per-operation execution is a follow-up.
"""

from __future__ import annotations

from enrichment.base import (
    EnrichmentContext,
    EnrichmentOperation,
    OperationResult,
)
from enrichment.company_website import CompanyWebsiteExtraction
from enrichment.linkedin_poc import LinkedInPocLookup
from enrichment.yc_directory_lookup import YCDirectoryLookup

ENRICHMENT_OPERATIONS: list[EnrichmentOperation] = [
    LinkedInPocLookup(),
    YCDirectoryLookup(),
    CompanyWebsiteExtraction(),
]

# Empty; pipeline.py still imports this name but no source_map rule points to
# the new operations yet (see docstring).
ENRICHMENT_BY_SOURCE_NAME: dict[str, EnrichmentOperation] = {}

__all__ = [
    "ENRICHMENT_BY_SOURCE_NAME",
    "ENRICHMENT_OPERATIONS",
    "EnrichmentContext",
    "EnrichmentOperation",
    "OperationResult",
]
