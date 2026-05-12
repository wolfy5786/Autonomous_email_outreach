"""Enrichment source registry keyed by ``source_name`` (matches attribute map)."""

from __future__ import annotations

from enrichment.base import EnrichmentContext, EnrichmentResult, EnrichmentSource
from enrichment.careers_page import CareersPageEnrichment
from enrichment.company_website import CompanyWebsiteEnrichment
from enrichment.sec_edgar import SecEdgarEnrichment
from enrichment.serp import SerpEnrichment

ENRICHMENT_BY_SOURCE_NAME: dict[str, EnrichmentSource] = {
    "company_website": CompanyWebsiteEnrichment(),
    "careers_page": CareersPageEnrichment(),
    "serp": SerpEnrichment(),
    "sec_edgar": SecEdgarEnrichment(),
}

__all__ = [
    "ENRICHMENT_BY_SOURCE_NAME",
    "EnrichmentContext",
    "EnrichmentResult",
    "EnrichmentSource",
]
