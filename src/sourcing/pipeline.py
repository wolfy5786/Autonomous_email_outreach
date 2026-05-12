"""
First slice of the sourcing pipeline: validate job, load plan, stub cache + source map.

Queue contract: ``sourcing.requested`` — see README and ``docs/data-sourcing-service.md``.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from cache_check import (
    CacheDecision,
    DiscoveryCacheResult,
    SourcingCacheResult,
    build_discovery_cache_decisions,
    build_sourcing_cache_decisions,
    discovery_cache_check,
    resolve_freshness_days,
    sourcing_cache_check,
)
from discovery import DISCOVERY_SOURCES, DiscoveryContext
from enrichment import ENRICHMENT_BY_SOURCE_NAME, EnrichmentContext
from shared.models.company import CompanyRecord, Headquarters
from shared.models.enums import HintCategory, SourceType
from shared.models.hint import Hint
from shared.models.plan import PlanRecord
from publisher import SourcingAMQPPublisher
from source_map import AttributeSourceMapRule, build_source_map
from validation.candidate import validate_candidates
from validation.enrichment import validate_enrichment

logger = logging.getLogger("sourcing.pipeline")


class PlanNotFoundError(LookupError):
    """Raised when ``plan_id`` has no matching ``PlanRecord`` (consumer should nack)."""


class SourcingJobConfig(BaseModel):
    """Optional orchestrator overrides (stub: accepted, not yet applied)."""

    model_config = {"extra": "allow"}

    max_companies: int | None = None
    discovery_mode: str | None = None
    freshness_override_days: int | None = None


class SourcingJobSeeds(BaseModel):
    """Optional seed hints for discovery (stub: accepted, not yet applied)."""

    model_config = {"extra": "allow"}

    domains: list[str] = Field(default_factory=list)
    company_names: list[str] = Field(default_factory=list)


class SourcingRequestedJob(BaseModel):
    """
    Payload for ``sourcing.requested``.

    Core fields match README; extra keys are ignored for forward compatibility.
    """

    model_config = {"extra": "ignore"}

    campaign_id: str
    plan_id: str
    target_entities: list[Any] = Field(default_factory=list)
    request_id: str | None = None
    config: SourcingJobConfig | None = None
    seeds: SourcingJobSeeds | None = None


class SourcingPipeline:
    """Orchestrates logged stages for the first pipeline slice."""

    def __init__(self, publisher: SourcingAMQPPublisher | None = None) -> None:
        self._publisher = publisher

    async def run(self, body: bytes) -> None:
        logger.info(
            "stage=message_received bytes=%s",
            len(body),
        )

        try:
            raw = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(
                "stage=parse_skipped reason=invalid_json error=%s preview=%r",
                e,
                body[:500],
            )
            return

        if not isinstance(raw, dict):
            logger.warning(
                "stage=parse_skipped reason=not_object type=%s",
                type(raw).__name__,
            )
            return

        try:
            job = SourcingRequestedJob.model_validate(raw)
        except ValidationError as e:
            logger.error("stage=job_validation_failed errors=%s", e.errors())
            raise

        logger.info(
            "stage=job_accepted campaign_id=%s plan_id=%s request_id=%s target_entities_count=%s",
            job.campaign_id,
            job.plan_id,
            job.request_id,
            len(job.target_entities),
        )

        plan = await PlanRecord.get(job.plan_id)
        if plan is None:
            logger.error(
                "stage=plan_load_failed plan_id=%s campaign_id=%s",
                job.plan_id,
                job.campaign_id,
            )
            raise PlanNotFoundError(f"No PlanRecord for plan_id={job.plan_id!r}")

        hints = (plan.outreach_context.personalization_hints if plan.outreach_context else None) or []
        logger.info(
            "stage=plan_loaded plan_id=%s campaign_id=%s sources=%s personalization_hints=%s",
            plan.id,
            plan.campaign_id,
            len(plan.sources),
            len(hints),
        )

        fresh_days = resolve_freshness_days(
            job.config.freshness_override_days if job.config else None
        )
        _, disc_cache = await self._discovery_cache(job, fresh_days)
        _, src_cache = await self._sourcing_cache(job, fresh_days)

        source_map = build_source_map(plan)
        logger.info(
            "stage=source_map_built rules_count=%s attributes=%s",
            len(source_map),
            sorted({r.attribute for r in source_map}),
        )

        raw_candidates = await self._run_discovery(job, plan)
        accepted, _rejected = await self._validate_candidates_stage(raw_candidates, plan)
        persisted = await self._persist_candidates_stage(accepted, plan, job.campaign_id)

        companies_for_enrichment = self._merge_companies_for_enrichment(
            disc_cache, src_cache, persisted=persisted
        )
        await self._run_enrichment(job, plan, source_map, companies_for_enrichment)
        self._validate_enrichment_stage(source_map)

        logger.info(
            "stage=pipeline_slice_completed campaign_id=%s plan_id=%s request_id=%s",
            job.campaign_id,
            job.plan_id,
            job.request_id,
        )

        await self._publish_completed(job, persisted, companies_for_enrichment)

    async def _publish_completed(
        self,
        job: SourcingRequestedJob,
        persisted: list[CompanyRecord],
        companies_for_enrichment: list[Any],
    ) -> None:
        if self._publisher is None:
            logger.debug(
                "stage=publish_completed_skipped reason=no_publisher campaign_id=%s",
                job.campaign_id,
            )
            return

        payload = {
            "campaign_id": job.campaign_id,
            "plan_id": job.plan_id,
            "request_id": job.request_id,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "companies_persisted": len(persisted),
            "companies_enriched": len(companies_for_enrichment),
        }
        try:
            await self._publisher.publish_completed(payload)
        except Exception as e:
            logger.warning(
                "stage=publish_completed_failed campaign_id=%s error=%s",
                job.campaign_id,
                e,
                exc_info=True,
            )

    async def _discovery_cache(
        self,
        job: SourcingRequestedJob,
        fresh_days: int,
    ) -> tuple[list[CacheDecision], DiscoveryCacheResult]:
        discovery = await discovery_cache_check(job.campaign_id)
        decisions = await build_discovery_cache_decisions(
            job.target_entities,
            discovery=discovery,
            freshness_days=fresh_days,
        )
        if not decisions and (
            job.seeds and (job.seeds.domains or job.seeds.company_names)
        ):
            logger.info(
                "stage=discovery_cache note=discovery_only_seeds campaign_id=%s domains=%s names=%s",
                job.campaign_id,
                job.seeds.domains,
                job.seeds.company_names,
            )
        logger.info(
            "stage=discovery_cache campaign_id=%s freshness_days=%s decisions_count=%s sample=%s",
            job.campaign_id,
            fresh_days,
            len(decisions),
            [
                {
                    "target_index": d.target_index,
                    "scrape_mode": d.scrape_mode.value,
                    "reason": d.reason,
                }
                for d in decisions[:3]
            ],
        )
        return decisions, discovery

    async def _sourcing_cache(
        self,
        job: SourcingRequestedJob,
        fresh_days: int,
    ) -> tuple[list[CacheDecision], SourcingCacheResult]:
        sourcing = await sourcing_cache_check(job.campaign_id)
        decisions = await build_sourcing_cache_decisions(
            job.target_entities,
            sourcing=sourcing,
            freshness_days=fresh_days,
        )
        logger.info(
            "stage=sourcing_cache campaign_id=%s freshness_days=%s decisions_count=%s sample=%s",
            job.campaign_id,
            fresh_days,
            len(decisions),
            [
                {
                    "target_index": d.target_index,
                    "scrape_mode": d.scrape_mode.value,
                    "reason": d.reason,
                }
                for d in decisions[:3]
            ],
        )
        return decisions, sourcing

    async def _run_discovery(
        self,
        job: SourcingRequestedJob,
        plan: PlanRecord,
    ) -> list[dict[str, Any]]:
        """Execute registered discovery sources; stubs log ``not_implemented``."""
        ctx = DiscoveryContext(
            campaign_id=job.campaign_id,
            plan=plan,
            config=job.config,
            seeds=job.seeds,
        )
        all_candidates: list[dict[str, Any]] = []
        for src in DISCOVERY_SOURCES:
            try:
                result = await src.discover(ctx)
                for c in result.candidates:
                    c.setdefault("_discovery_source", src.source_name)
                    c.setdefault("_discovery_tier", src.tier)
                all_candidates.extend(result.candidates)
                if result.errors:
                    logger.warning(
                        "stage=discovery_source_errors source=%s errors=%s",
                        src.source_name,
                        result.errors[:3],
                    )
                logger.info(
                    "stage=discovery_source_ok source=%s candidates=%s",
                    src.source_name,
                    len(result.candidates),
                )
            except NotImplementedError:
                logger.info("stage=discovery_not_implemented source=%s", src.source_name)
            except Exception as e:
                logger.warning(
                    "stage=discovery_error source=%s error=%s",
                    src.source_name,
                    e,
                    exc_info=True,
                )
        logger.info(
            "stage=discovery_aggregate campaign_id=%s total_candidates=%s",
            job.campaign_id,
            len(all_candidates),
        )
        return all_candidates

    async def _validate_candidates_stage(
        self,
        candidates: list[dict[str, Any]],
        plan: PlanRecord,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        try:
            accepted, rejected = validate_candidates(candidates, plan)
            logger.info(
                "stage=candidate_validation campaign_id=%s accepted=%s rejected=%s",
                plan.campaign_id,
                len(accepted),
                len(rejected),
            )
            return accepted, rejected
        except NotImplementedError:
            logger.info(
                "stage=candidate_validation_not_implemented campaign_id=%s candidates=%s",
                plan.campaign_id,
                len(candidates),
            )
            return candidates, []

    async def _persist_candidates_stage(
        self,
        accepted: list[dict[str, Any]],
        plan: PlanRecord,
        campaign_id: str,
    ) -> list[CompanyRecord]:
        """
        Upsert Tier A candidates as ``CompanyRecord`` rows; attach Tier B candidates as
        ``Hint`` rows on the matching company. Returns persisted companies for enrichment.
        """
        if not accepted:
            logger.info("stage=persist_candidates campaign_id=%s skipped=empty", campaign_id)
            return []

        now = datetime.now(timezone.utc)
        tier_a = [c for c in accepted if (c.get("_discovery_tier") or "") == "A"]
        tier_b = [c for c in accepted if (c.get("_discovery_tier") or "") == "B"]

        persisted_by_domain: dict[str, CompanyRecord] = {}
        inserted = 0
        updated = 0
        company_errors = 0

        for c in tier_a:
            domain = c.get("domain")
            if not isinstance(domain, str) or not domain:
                continue
            try:
                existing = await CompanyRecord.find_one(CompanyRecord.domain == domain)
                if existing is None:
                    record = _candidate_to_company_record(c, campaign_id, now)
                    await record.insert()
                    persisted_by_domain[domain] = record
                    inserted += 1
                else:
                    if campaign_id not in existing.campaign_ids:
                        existing.campaign_ids.append(campaign_id)
                    existing.freshness_timestamp = now
                    await existing.save()
                    persisted_by_domain[domain] = existing
                    updated += 1
            except Exception as e:
                company_errors += 1
                logger.warning(
                    "stage=persist_company_error campaign_id=%s domain=%s error=%s",
                    campaign_id, domain, e, exc_info=True,
                )

        hints_inserted = 0
        hints_skipped = 0
        hint_errors = 0

        for c in tier_b:
            domain = c.get("domain")
            if not isinstance(domain, str) or not domain:
                continue
            try:
                company = persisted_by_domain.get(domain)
                if company is None:
                    company = await CompanyRecord.find_one(CompanyRecord.domain == domain)
                if company is None:
                    continue

                source_name = c.get("_discovery_source") or "unknown"
                source_url = c.get("url") or None
                dup_query = {
                    "company_id": company.id,
                    "source_name": source_name,
                    "source_url": source_url,
                }
                existing_hint = await Hint.find_one(dup_query)
                if existing_hint is not None:
                    hints_skipped += 1
                    continue

                summary = (
                    c.get("raw_title")
                    or c.get("name")
                    or f"signal from {source_name}"
                )
                hint = Hint(
                    company_id=company.id,
                    campaign_id=campaign_id,
                    category=HintCategory.PRODUCT_LAUNCH,
                    summary=summary,
                    source_name=source_name,
                    source_type=SourceType.HINT_FEED,
                    source_url=source_url,
                    raw_snippet=c.get("raw_title"),
                )
                await hint.insert()
                hints_inserted += 1
            except Exception as e:
                hint_errors += 1
                logger.warning(
                    "stage=persist_hint_error campaign_id=%s domain=%s error=%s",
                    campaign_id, domain, e, exc_info=True,
                )

        logger.info(
            "stage=persist_candidates campaign_id=%s tier_a_inserted=%s tier_a_updated=%s "
            "tier_b_hints_inserted=%s tier_b_hints_skipped=%s company_errors=%s hint_errors=%s",
            campaign_id,
            inserted,
            updated,
            hints_inserted,
            hints_skipped,
            company_errors,
            hint_errors,
        )
        return list(persisted_by_domain.values())

    def _merge_companies_for_enrichment(
        self,
        disc_cache: DiscoveryCacheResult,
        src_cache: SourcingCacheResult,
        persisted: list[CompanyRecord] | None = None,
    ) -> list[Any]:
        """Dedupe companies from discovery cache + sourcing cache + freshly-persisted candidates."""
        merged: list[Any] = []
        seen: set[str] = set()
        sources: list[list[Any]] = [disc_cache.companies, src_cache.companies]
        if persisted:
            sources.append(persisted)
        for source in sources:
            for c in source:
                if c.id in seen:
                    continue
                seen.add(c.id)
                merged.append(c)
        return merged

    async def _run_enrichment(
        self,
        job: SourcingRequestedJob,
        plan: PlanRecord,
        source_map: list[AttributeSourceMapRule],
        companies: list[Any],
    ) -> None:
        if not companies:
            logger.info(
                "stage=enrichment_skip campaign_id=%s reason=no_companies_in_cache",
                job.campaign_id,
            )
            return

        enrichment_rules = [r for r in source_map if r.allowed_for_enrichment]
        sorted_rules = sorted(
            enrichment_rules,
            key=lambda r: (r.priority, r.attribute, r.source_name),
        )
        for company in companies:
            missing_fields: list[str] = []
            for rule in sorted_rules:
                impl = ENRICHMENT_BY_SOURCE_NAME.get(rule.source_name)
                if impl is None:
                    logger.debug(
                        "stage=enrichment_no_handler campaign_id=%s source_name=%s attribute=%s",
                        job.campaign_id,
                        rule.source_name,
                        rule.attribute,
                    )
                    continue
                ctx = EnrichmentContext(
                    campaign_id=job.campaign_id,
                    company=company,
                    plan=plan,
                    missing_fields=missing_fields,
                )
                try:
                    result = await impl.enrich(ctx)
                    logger.info(
                        "stage=enrichment_source_ok campaign_id=%s company_id=%s source=%s attribute=%s keys=%s",
                        job.campaign_id,
                        company.id,
                        rule.source_name,
                        rule.attribute,
                        list(result.attributes.keys()),
                    )
                except NotImplementedError:
                    logger.info(
                        "stage=enrichment_not_implemented campaign_id=%s company_id=%s source=%s attribute=%s",
                        job.campaign_id,
                        company.id,
                        rule.source_name,
                        rule.attribute,
                    )
                except Exception as e:
                    logger.warning(
                        "stage=enrichment_error campaign_id=%s company_id=%s source=%s error=%s",
                        job.campaign_id,
                        company.id,
                        rule.source_name,
                        e,
                        exc_info=True,
                    )

    def _validate_enrichment_stage(self, source_map: list[AttributeSourceMapRule]) -> None:
        if not source_map:
            return
        try:
            validate_enrichment(None, source_map[0])
        except NotImplementedError:
            logger.info(
                "stage=enrichment_validation_not_implemented sample_rule_source=%s",
                source_map[0].source_name,
            )


_EXTRA_KEYS_FROM_CANDIDATE: tuple[str, ...] = (
    "yc_id",
    "yc_slug",
    "yc_batch",
    "yc_batch_year",
    "yc_status",
    "is_b2b_saas",
    "tags",
)


def _candidate_to_company_record(
    candidate: dict[str, Any],
    campaign_id: str,
    now: datetime,
) -> CompanyRecord:
    """Map an accepted Tier A candidate dict to a fresh ``CompanyRecord`` for insert."""
    hq_data = candidate.get("headquarters") or {}
    headquarters: Headquarters | None = None
    if isinstance(hq_data, dict) and (hq_data.get("city") or hq_data.get("country")):
        headquarters = Headquarters(
            city=hq_data.get("city") or None,
            country=hq_data.get("country") or None,
        )

    extra: dict[str, Any] = {}
    for key in _EXTRA_KEYS_FROM_CANDIDATE:
        value = candidate.get(key)
        if value is not None:
            extra[key] = value

    return CompanyRecord(
        name=candidate.get("name") or candidate["domain"],
        domain=candidate["domain"],
        industry=candidate.get("industry"),
        employee_count=candidate.get("employee_count"),
        headquarters=headquarters,
        description=candidate.get("description"),
        website_url=candidate.get("website_url"),
        campaign_ids=[campaign_id],
        freshness_timestamp=now,
        extra=extra,
    )
