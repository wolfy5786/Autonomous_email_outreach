from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import structlog
from pydantic import ValidationError

from .contracts import (
    CampaignDocument,
    CompanyDocument,
    PersonDocument,
    PlanDocument,
    ProspectingCompletedEvent,
    ProspectingRequestedEvent,
    RankedProspect,
)
from .errors import PermanentProcessingError, RetryableProcessingError
from .db import Mongo
from .scoring import combined_score, score_company, score_person

logger = structlog.get_logger("prospecting.worker").bind(service="prospecting")


@dataclass(frozen=True)
class Prospect:
    company_id: str
    poc_id: str
    score: float


class ProspectingWorker:
    def __init__(self, mongo: Mongo, default_min_icp_score: float):
        self._mongo = mongo
        self._default_min = default_min_icp_score

    def handle_prospecting_requested(self, msg: dict[str, Any]) -> dict[str, Any]:
        """
        Input: { campaign_id, plan_id, entity_ids[] }
        Output: { campaign_id, ranked_prospects[] }
        """
        # validate incoming request
        try:
            event = ProspectingRequestedEvent.model_validate(msg)
        except ValidationError as exc:
            raise PermanentProcessingError(f"request validation failed: {exc}") from exc

        campaign_id = event.campaign_id
        plan_id = event.plan_id
        company_ids = [str(x) for x in event.entity_ids if x is not None]

        logger.info(
            "request_validated",
            stage="request_validated",
            campaign_id=campaign_id,
            plan_id=plan_id,
            event_id=getattr(event, "event_id", None) or msg.get("event_id"),
            idempotency_key=msg.get("idempotency_key"),
            trace_id=msg.get("trace_id"),
            entity_count=len(company_ids),
            entity_ids_sample=company_ids[:5],
        )

        # campaign lookup
        campaign_doc = self._mongo.get_campaign(campaign_id)
        campaign = None
        if campaign_doc:
            try:
                campaign = CampaignDocument.model_validate(campaign_doc).model_dump(mode="python")
            except ValidationError as exc:
                cid = str(campaign_doc.get("id") or campaign_doc.get("_id") or campaign_doc.get("campaign_id"))
                raise PermanentProcessingError(f"campaign document validation failed for id={cid}: {exc}") from exc

        logger.info(
            "campaign_lookup",
            stage="campaign_lookup",
            status=("found" if campaign else "missing"),
            campaign_id=campaign_id,
            campaign_status=(campaign.get("status") if campaign else None),
            campaign_plan_id=(campaign.get("plan_id") if campaign else None),
        )

        if not campaign:
            raise PermanentProcessingError(f"campaign not found for campaign_id={campaign_id}")

        # plan lookup
        plan_doc = self._mongo.get_plan(campaign_id=campaign_id)
        plan = None
        if plan_doc:
            try:
                plan = PlanDocument.model_validate(plan_doc).model_dump(mode="python")
            except ValidationError as exc:
                pid = str(plan_doc.get("id") or plan_doc.get("_id") or "")
                raise PermanentProcessingError(f"plan document validation failed for id={pid}: {exc}") from exc

        logger.info(
            "plan_lookup",
            stage="plan_lookup",
            status=("found" if plan else "missing"),
            campaign_id=campaign_id,
            plan_id=(plan.get("id") if plan else None),
        )

        if not plan:
            if campaign and str(campaign.get("status") or "").lower() in {"draft", "creating", "pending", "initializing"}:
                raise RetryableProcessingError(f"plan not ready for campaign_id={campaign_id}")
            raise PermanentProcessingError(f"plan not found for campaign_id={campaign_id}")

        # determine min score
        min_score = self._default_min
        try:
            cfg = (campaign or {}).get("config") or {}
            if "min_icp_score" in cfg:
                min_score = float(cfg["min_icp_score"])
        except (TypeError, ValueError):
            logger.warning(
                "invalid_min_icp_score",
                stage="invalid_min_icp_score",
                campaign_id=campaign_id,
            )

        # load companies
        company_docs = self._mongo.get_companies(company_ids)
        companies: list[dict[str, Any]] = []
        company_validation_errors = 0
        skipped_not_enriched = 0
        for doc in company_docs:
            try:
                validated = CompanyDocument.model_validate(doc)
                if not validated.enriched:
                    skipped_not_enriched += 1
                    continue
                companies.append(validated.model_dump(mode="python"))
            except ValidationError:
                company_validation_errors += 1

        logger.info(
            "companies_loaded",
            stage="companies_loaded",
            campaign_id=campaign_id,
            requested_count=len(company_ids),
            found_count=len(company_docs),
            missing_count=max(0, len(company_ids) - len(company_docs)),
            company_validation_errors=company_validation_errors,
            skipped_not_enriched=skipped_not_enriched,
        )

        if not companies:
            logger.info(
                "ranking_completed",
                stage="ranking_completed",
                status="success",
                campaign_id=campaign_id,
                ranked_count=0,
                outcome_reason="no_companies_found",
            )
            return {"campaign_id": campaign_id, "ranked_prospects": []}

        # load persons
        person_docs = self._mongo.get_persons_for_companies([str(c.get("id") or c.get("_id")) for c in companies])
        persons: list[dict[str, Any]] = []
        person_validation_errors = 0
        for doc in person_docs:
            try:
                persons.append(PersonDocument.model_validate(doc).model_dump(mode="python"))
            except ValidationError:
                person_validation_errors += 1

        logger.info(
            "persons_loaded",
            stage="persons_loaded",
            campaign_id=campaign_id,
            person_count=len(persons),
            person_validation_errors=person_validation_errors,
        )

        persons_by_company: dict[str, list[dict[str, Any]]] = {}
        for p in persons:
            cid = p.get("company_id")
            if cid is None:
                continue
            persons_by_company.setdefault(str(cid), []).append(p)

        prospects: list[dict[str, Any]] = []

        # collect prospect tuples with full scoring metadata
        # extract event metadata if present for idempotency tracking
        event_id = None
        try:
            event_id = getattr(event, "event_id", None) or msg.get("event_id")
        except Exception:
            event_id = None

        filtered_count = 0

        for c in companies:
            cid = str(c.get("id") or c.get("_id") or "")
            if not cid:
                continue
            c_score = score_company(c, plan)

            # persist company-level score with campaign-scoped record
            company_reasons = {k: v.reason for k, v in c_score.dimension_scores.items()}
            scored_at = datetime.utcnow().isoformat()
            self._mongo.update_company_score(
                cid,
                campaign_id,
                c_score.score,
                c_score.scoring_version,
                scored_at=scored_at,
                reasons=company_reasons,
                event_id=event_id,
            )

            for p in persons_by_company.get(cid, []):
                pid = str(p.get("id") or p.get("_id") or "")
                if not pid:
                    continue
                p_score = score_person(p, plan)
                total = combined_score(c_score, p_score)

                person_reasons = {k: v.reason for k, v in p_score.dimension_scores.items()}
                self._mongo.update_person_score(
                    pid,
                    campaign_id,
                    p_score.score,
                    p_score.scoring_version,
                    scored_at=scored_at,
                    reasons=person_reasons,
                    event_id=event_id,
                )
                if p.get("email"):
                    self._mongo.update_person_email_verified(pid, True)

                if total < min_score:
                    filtered_count += 1
                    logger.debug(
                        "prospect_filtered",
                        stage="prospect_filtered",
                        campaign_id=campaign_id,
                        company_id=cid,
                        poc_id=pid,
                        total_score=round(total, 6),
                        min_icp_score=min_score,
                    )
                    continue

                # extract tie-breaker values
                company_data_completeness = 0.0
                try:
                    company_data_completeness = float(
                        getattr(c_score.dimension_scores.get("data_completeness"), "score", 0.0)
                    )
                except Exception:
                    company_data_completeness = 0.0

                person_email_verified = bool(p.get("email_verified") or (p_score.dimension_scores.get("email_verified") and p_score.dimension_scores.get("email_verified").score > 0))

                freshness_ts = c.get("freshness_timestamp") or 0
                try:
                    # numeric timestamps should sort descending; keep raw if numeric
                    freshness_sort = float(freshness_ts) if isinstance(freshness_ts, (int, float)) else 0
                except Exception:
                    freshness_sort = 0

                prospects.append(
                    {
                        "company_id": cid,
                        "poc_id": pid,
                        "company_score": round(c_score.score, 6),
                        "person_score": round(p_score.score, 6),
                        "total_score": round(total, 6),
                        "scoring_version": c_score.scoring_version or p_score.scoring_version,
                        "company_data_completeness": float(company_data_completeness),
                        "person_email_verified": person_email_verified,
                        "freshness_sort": float(freshness_sort),
                        "company_reasons": {k: v.reason for k, v in c_score.dimension_scores.items()},
                        "person_reasons": {k: v.reason for k, v in p_score.dimension_scores.items()},
                    }
                )

        # report filtering summary
        logger.info(
            "prospect_filtered",
            stage="prospect_filtered",
            campaign_id=campaign_id,
            filtered_count=filtered_count,
            min_icp_score=min_score,
        )

        # sort using the requested tie-breakers
        prospects.sort(
            key=lambda r: (
                -float(r.get("total_score", 0.0)),
                -float(r.get("company_data_completeness", 0.0)),
                -int(bool(r.get("person_email_verified", False))),
                -float(r.get("freshness_sort", 0.0)),
                r.get("company_id", ""),
                r.get("poc_id", ""),
            )
        )

        # apply max_drafts if present
        max_drafts = None
        try:
            cfg = (campaign or {}).get("config") or {}
            if "max_drafts" in cfg:
                max_drafts = int(cfg["max_drafts"])
                if max_drafts <= 0:
                    max_drafts = None
        except Exception:
            max_drafts = None

        if max_drafts is not None:
            prospects = prospects[:max_drafts]

        # build RankedProspect models with rank and reasons summary
        ranked: list[RankedProspect] = []
        for idx, r in enumerate(prospects, start=1):
            reasons = {
                "company": r.get("company_reasons", {}),
                "poc": r.get("person_reasons", {}),
            }
            ranked.append(
                RankedProspect(
                    rank=idx,
                    company_id=r["company_id"],
                    poc_id=r["poc_id"],
                    icp_fit_score=float(r["company_score"]),
                    icp_poc_score=float(r["person_score"]),
                    total_score=float(r["total_score"]),
                    scoring_version=str(r.get("scoring_version") or ""),
                    scoring_reasons=reasons,
                )
            )

        output = ProspectingCompletedEvent(
            campaign_id=campaign_id,
            ranked_prospects=ranked,
        )
        # return a python dict so callers (and publisher) can work with structured data
        ranked_count = len(ranked)
        outcome_reason = None
        if ranked_count == 0:
            if not companies:
                outcome_reason = "no_companies_found"
            elif not persons:
                outcome_reason = "no_persons_found"
            else:
                outcome_reason = "all_filtered_by_min_icp_score"
        logger.info(
            "ranking_completed",
            stage="ranking_completed",
            status="success",
            campaign_id=campaign_id,
            ranked_count=ranked_count,
            outcome_reason=outcome_reason,
        )

        return output.model_dump(mode="python", exclude_none=True)
