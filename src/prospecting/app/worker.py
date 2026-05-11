from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .contracts import (
    CampaignDocument,
    CompanyDocument,
    PersonDocument,
    PlanDocument,
    ProspectingCompletedEvent,
    RankedProspect,
    SourcingCompletedEvent,
)
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

    def handle_sourcing_completed(self, msg: dict[str, Any]) -> dict[str, Any]:
        """
        Input: { campaign_id, entity_ids[] }
        Output: { campaign_id, ranked_prospects[] }
        """
        event = SourcingCompletedEvent.model_validate(msg)
        campaign_id = event.campaign_id
        company_ids = [str(x) for x in event.entity_ids if x is not None]

        plan_doc = self._mongo.get_plan(campaign_id=campaign_id)
        plan = PlanDocument.model_validate(plan_doc).model_dump(mode="python") if plan_doc else None
        if not plan:
            raise RuntimeError(f"plan not found for campaign_id={campaign_id}")

        campaign_doc = self._mongo.get_campaign(campaign_id)
        campaign = CampaignDocument.model_validate(campaign_doc).model_dump(mode="python") if campaign_doc else None
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

        prospects: list[Prospect] = []

        for c in companies:
            cid = str(c.get("id") or c.get("_id") or "")
            if not cid:
                continue
            c_score = score_company(c, plan)

            self._mongo.update_company_score(cid, campaign_id, c_score.score, c_score.scoring_version)

            for p in persons_by_company.get(cid, []):
                pid = str(p.get("id") or p.get("_id") or "")
                if not pid:
                    continue
                p_score = score_person(p, plan)
                total = combined_score(c_score, p_score)

                self._mongo.update_person_score(pid, campaign_id, p_score.score, p_score.scoring_version)
                if p.get("email"):
                    self._mongo.update_person_email_verified(pid, True)

                if total >= min_score:
                    prospects.append(Prospect(company_id=cid, poc_id=pid, score=total))

        prospects.sort(key=lambda x: x.score, reverse=True)

        ranked = [RankedProspect(company_id=p.company_id, poc_id=p.poc_id, score=round(p.score, 6)) for p in prospects]
        output = ProspectingCompletedEvent(
            campaign_id=campaign_id,
            ranked_prospects=ranked,
        )
        return output.model_dump(mode="json", exclude_none=True)

