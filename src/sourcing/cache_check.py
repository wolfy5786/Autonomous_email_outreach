"""
Mongo-backed cache lookups for the sourcing pipeline.

``discovery_cache_check`` loads ``CompanyRecord`` rows already linked to a campaign.
``sourcing_cache_check`` loads ``Hint`` rows for a campaign, then resolves related
``CompanyRecord`` documents by ``company_id`` (those companies may belong to other campaigns).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from shared.models.company import CompanyRecord
from shared.models.enums import ScrapeMode
from shared.models.hint import Hint

logger = logging.getLogger("sourcing.cache_check")

DEFAULT_FRESHNESS_DAYS = 30


@dataclass
class DiscoveryCacheResult:
    """Companies already associated with ``campaign_id`` (discovery cache hit)."""

    campaign_id: str
    companies: list[CompanyRecord] = field(default_factory=list)


@dataclass
class SourcingCacheResult:
    """Hints for a campaign plus resolved companies (may span campaigns via ``company_id``)."""

    campaign_id: str
    hints: list[Hint] = field(default_factory=list)
    companies: list[CompanyRecord] = field(default_factory=list)


@dataclass
class CacheDecision:
    """Scrape mode for one ``target_entities`` entry after cache evaluation."""

    target_index: int
    target_entity: Any
    scrape_mode: ScrapeMode
    reason: str


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_domain(value: str) -> str:
    """Lowercase hostname-style domain (best-effort strip of scheme/path)."""
    s = value.strip().lower()
    s = re.sub(r"^https?://", "", s)
    s = s.split("/")[0]
    if s.startswith("www."):
        s = s[4:]
    return s


def compute_scrape_mode_for_company(
    company: CompanyRecord | None,
    *,
    freshness_days: int,
    now: datetime | None = None,
) -> tuple[ScrapeMode, str]:
    """
    Apply README cache-first rules: none / partial / all from record + freshness window.
    """
    if company is None:
        return ScrapeMode.ALL, "no_company_in_cache"
    now = _ensure_utc(now or _utcnow())
    ts = _ensure_utc(company.freshness_timestamp)
    if now - ts > timedelta(days=freshness_days):
        return ScrapeMode.PARTIAL, "stale_cache"
    # TODO: uncomment this when we have a way to check data completeness    
    # if company.data_completeness < 1.0:
    #     return ScrapeMode.PARTIAL, "incomplete_data"
    return ScrapeMode.NONE, "fresh_complete_cache"


def compute_scrape_mode_for_hint(
    hint: Hint | None,
    *,
    freshness_days: int,
    now: datetime | None = None,
) -> tuple[ScrapeMode, str]:
    """Sourcing cache: freshness only, using ``Hint.discovered_at``."""
    if hint is None:
        return ScrapeMode.ALL, "no_hint_in_cache"
    now = _ensure_utc(now or _utcnow())
    ts = _ensure_utc(hint.discovered_at)
    if now - ts > timedelta(days=freshness_days):
        return ScrapeMode.PARTIAL, "stale_hint_cache"
    return ScrapeMode.NONE, "fresh_hint_cache"


def _newest_hint_for_company(company_id: str, hints: list[Hint]) -> Hint | None:
    matching = [h for h in hints if h.company_id == company_id]
    if not matching:
        return None
    return max(matching, key=lambda h: _ensure_utc(h.discovered_at))


async def discovery_cache_check(campaign_id: str) -> DiscoveryCacheResult:
    """
    Find ``CompanyRecord`` documents that list ``campaign_id`` in ``campaign_ids``.
    """
    companies = await CompanyRecord.find(
        {"campaign_ids": campaign_id},
    ).to_list()
    logger.info(
        "stage=discovery_cache_check campaign_id=%s companies_found=%s",
        campaign_id,
        len(companies),
    )
    return DiscoveryCacheResult(campaign_id=campaign_id, companies=companies)


async def sourcing_cache_check(
    campaign_id: str,
) -> SourcingCacheResult:
    """
    Load hints for ``campaign_id``, then load each referenced ``CompanyRecord`` by id.
    """
    hints = await Hint.find(Hint.campaign_id == campaign_id).to_list()
    id_order: list[str] = []
    seen: set[str] = set()
    for h in hints:
        if h.company_id not in seen:
            seen.add(h.company_id)
            id_order.append(h.company_id)

    companies: list[CompanyRecord] = []
    if id_order:
        found = await CompanyRecord.find({"_id": {"$in": id_order}}).to_list()
        by_id = {c.id: c for c in found}
        companies = [by_id[cid] for cid in id_order if cid in by_id]

    logger.info(
        "stage=sourcing_cache_check campaign_id=%s hints=%s companies_resolved=%s",
        campaign_id,
        len(hints),
        len(companies),
    )
    return SourcingCacheResult(
        campaign_id=campaign_id,
        hints=hints,
        companies=companies,
    )


def _company_indexes_from_list(
    companies: list[CompanyRecord],
) -> tuple[dict[str, CompanyRecord], dict[str, CompanyRecord]]:
    by_id: dict[str, CompanyRecord] = {}
    by_domain: dict[str, CompanyRecord] = {}
    for c in companies:
        by_id[c.id] = c
        by_domain[normalize_domain(c.domain)] = c
    return by_id, by_domain


def _resolve_company_from_target(
    entity: Any,
    by_id: dict[str, CompanyRecord],
    by_domain: dict[str, CompanyRecord],
) -> CompanyRecord | None:
    if isinstance(entity, dict):
        cid = entity.get("company_id") or entity.get("entity_id") or entity.get("id")
        if isinstance(cid, str) and cid in by_id:
            return by_id[cid]
        for key in ("domain", "website", "website_url", "url"):
            raw = entity.get(key)
            if isinstance(raw, str) and raw.strip():
                d = normalize_domain(raw)
                if d in by_domain:
                    return by_domain[d]
        return None
    if isinstance(entity, str) and entity.strip():
        d = normalize_domain(entity)
        return by_domain.get(d)
    return None


async def _lookup_company_by_domain(domain: str) -> CompanyRecord | None:
    d = normalize_domain(domain)
    return await CompanyRecord.find_one(CompanyRecord.domain == d)


async def _resolve_company_with_fallback(
    entity: Any,
    *,
    by_id: dict[str, CompanyRecord],
    by_domain: dict[str, CompanyRecord],
) -> tuple[CompanyRecord | None, str]:
    company = _resolve_company_from_target(entity, by_id, by_domain)
    resolution = "indexed"
    if company is None and isinstance(entity, dict):
        raw = entity.get("domain") or entity.get("website") or entity.get("website_url")
        if isinstance(raw, str) and raw.strip():
            company = await _lookup_company_by_domain(raw)
            if company is not None:
                resolution = "db_domain"
    elif company is None and isinstance(entity, str) and entity.strip():
        company = await _lookup_company_by_domain(entity)
        if company is not None:
            resolution = "db_domain"
    return company, resolution


async def build_discovery_cache_decisions(
    target_entities: list[Any],
    *,
    discovery: DiscoveryCacheResult,
    freshness_days: int,
) -> list[CacheDecision]:
    """
    One decision per target using only discovery cache companies (``campaign_ids`` match).
    """
    by_id, by_domain = _company_indexes_from_list(discovery.companies)
    decisions: list[CacheDecision] = []
    for i, entity in enumerate(target_entities):
        company, resolution = await _resolve_company_with_fallback(
            entity, by_id=by_id, by_domain=by_domain
        )
        mode, reason = compute_scrape_mode_for_company(
            company,
            freshness_days=freshness_days,
        )
        if company is not None:
            reason = f"{reason}|resolve={resolution}"

        decisions.append(
            CacheDecision(
                target_index=i,
                target_entity=entity,
                scrape_mode=mode,
                reason=reason,
            )
        )
    return decisions


async def build_sourcing_cache_decisions(
    target_entities: list[Any],
    *,
    sourcing: SourcingCacheResult,
    freshness_days: int,
) -> list[CacheDecision]:
    """
    One decision per target from hints for this campaign: freshness of ``Hint.discovered_at`` only.
    """
    by_id, by_domain = _company_indexes_from_list(sourcing.companies)
    decisions: list[CacheDecision] = []
    for i, entity in enumerate(target_entities):
        company, resolution = await _resolve_company_with_fallback(
            entity, by_id=by_id, by_domain=by_domain
        )
        hint = (
            _newest_hint_for_company(company.id, sourcing.hints)
            if company is not None
            else None
        )
        mode, reason = compute_scrape_mode_for_hint(
            hint,
            freshness_days=freshness_days,
        )
        if company is not None:
            reason = f"{reason}|resolve={resolution}"

        decisions.append(
            CacheDecision(
                target_index=i,
                target_entity=entity,
                scrape_mode=mode,
                reason=reason,
            )
        )
    return decisions


def resolve_freshness_days(override_days: int | None) -> int:
    if override_days is not None:
        return max(1, override_days)
    return DEFAULT_FRESHNESS_DAYS
