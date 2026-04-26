"""No-op sourcing pipeline stages with logs only."""

import logging
from dataclasses import dataclass
from typing import Any

from .contracts import SourcingRequestedEvent


@dataclass(frozen=True)
class PipelineResult:
    discovered_entity_ids: list[str]
    partial_entity_gaps: dict[str, list[str]]
    stats: dict[str, int]


class SourcingPipeline:
    def __init__(self, logger: logging.LoggerAdapter):
        self.logger = logger

    async def run(self, event: SourcingRequestedEvent) -> PipelineResult:
        self._log_stage("load_plan", event, "Loading plan document (skeleton).")
        self._log_stage("cache_check", event, "Applying cache-first decision (skeleton).")
        self._log_stage(
            "build_attribute_source_map",
            event,
            "Building attribute source map (skeleton).",
        )
        self._log_stage(
            "company_discovery", event, "Discovering candidates from configured sources (skeleton)."
        )
        self._log_stage(
            "candidate_validation",
            event,
            "Running candidate validation gates and dedup checks (skeleton).",
        )
        self._log_stage(
            "company_enrichment",
            event,
            "Executing layered enrichment (API + scraping placeholders).",
        )
        self._log_stage(
            "persist_records",
            event,
            "Persisting company records with provenance metadata (skeleton).",
        )

        return PipelineResult(
            discovered_entity_ids=[],
            partial_entity_gaps={},
            stats={
                "companies_discovered": 0,
                "companies_enriched": 0,
                "rejected_candidates": 0,
            },
        )

    def _log_stage(self, stage: str, event: SourcingRequestedEvent, message: str) -> None:
        self.logger.info(
            "stage=%s %s",
            stage,
            message,
            extra={"request_id": event.request_id or "-", "campaign_id": event.campaign_id},
        )

