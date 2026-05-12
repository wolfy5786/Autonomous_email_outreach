from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

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


logger = logging.getLogger(__name__)


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
        Input: { campaign_id, plan_id?, entity_ids[] }
        Output: { campaign_id, ranked_prospects[] }
        """
        event = ProspectingRequestedEvent.model_validate(msg)
        campaign_id = event.campaign_id
        company_ids = [str(x) for x in event.entity_ids if x is not None]

        campaign_doc = self._mongo.get_campaign(campaign_id)
        campaign = CampaignDocument.model_validate(campaign_doc).model_dump(mode="python") if campaign_doc else None
        if not campaign:
            raise PermanentProcessingError(f"campaign not found for campaign_id={campaign_id}")

        plan_doc = self._mongo.get_plan(campaign_id=campaign_id)
        plan = PlanDocument.model_validate(plan_doc).model_dump(mode="python") if plan_doc else None
        if not plan:
            if campaign and str(campaign.get("status") or "").lower() in {"draft", "creating", "pending", "initializing"}:
                raise RetryableProcessingError(f"plan not ready for campaign_id={campaign_id}")
            raise PermanentProcessingError(f"plan not found for campaign_id={campaign_id}")

        min_score = self._default_min
        try:
            cfg = (campaign or {}).get("config") or {}
            if "min_icp_score" in cfg:
                min_score = float(cfg["min_icp_score"])
        except (TypeError, ValueError) as exc:
            logger.warning(
                "invalid min_icp_score on campaign_id=%s; falling back to default",
                campaign_id,
                exc_info=exc,
            )

        company_docs = self._mongo.get_companies(company_ids)
        companies = [CompanyDocument.model_validate(doc).model_dump(mode="python") for doc in company_docs]
        if not companies:
            logger.info("no companies found for campaign_id=%s ids=%s", campaign_id, company_ids[:5])
            return {"campaign_id": campaign_id, "ranked_prospects": []}

        persons = [
            PersonDocument.model_validate(doc).model_dump(mode="python")
            for doc in self._mongo.get_persons_for_companies([str(c.get("id") or c.get("_id")) for c in companies])
        ]
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
        return output.model_dump(mode="python", exclude_none=True)

