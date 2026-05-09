"""SEC EDGAR Form D — efts.sec.gov structured API."""

from __future__ import annotations

from enrichment.base import EnrichmentContext, EnrichmentResult, EnrichmentSource


class SecEdgarEnrichment(EnrichmentSource):
    """
    Offering type, amount raised, filed date, SIC, state.

    Filter SIC 7372 / 8099 per map; 15-day filing lag typical.
    """

    source_name = "sec_edgar"

    async def enrich(self, ctx: EnrichmentContext) -> EnrichmentResult:
        raise NotImplementedError(
            "SecEdgarEnrichment.enrich: query EDGAR API for Form D; map to sec_form_d_amount, "
            "sec_form_d_filed_at, sec_sic_code with provenance."
        )
