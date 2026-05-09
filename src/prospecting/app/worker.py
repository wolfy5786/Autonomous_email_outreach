from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

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
        Input (README): { campaign_id, entity_ids[] }
        Output (README): { campaign_id, ranked_prospects[] }
        """
        campaign_id = str(msg.get("campaign_id") or "")
        if not campaign_id:
            raise ValueError("missing campaign_id")

        plan_id = msg.get("plan_id")
        if plan_id is not None:
            plan_id = str(plan_id)

        entity_ids = msg.get("entity_ids") or []
        if not isinstance(entity_ids, list):
            raise ValueError("entity_ids must be a list")
        company_ids = [str(x) for x in entity_ids if x is not None]

        plan = self._mongo.get_plan(plan_id=plan_id, campaign_id=campaign_id)
        if not plan:
            raise RuntimeError(f"plan not found for campaign_id={campaign_id}")

        campaign = self._mongo.get_campaign(campaign_id)
        min_score = self._default_min
        try:
            cfg = (campaign or {}).get("config") or {}
            if "min_icp_score" in cfg:
                min_score = float(cfg["min_icp_score"])
        except Exception:
            pass

        companies = self._mongo.get_companies(company_ids)
        if not companies:
            logger.info("no companies found for campaign_id=%s ids=%s", campaign_id, company_ids[:5])
            return {"campaign_id": campaign_id, "ranked_prospects": []}

        persons = self._mongo.get_persons_for_companies([c.get("id") or c.get("_id") for c in companies])
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

            # persist company score
            res = self._mongo.companies.update_one({"id": cid}, {"$set": {"icp_fit_score": c_score}}, upsert=False)
            if res.matched_count == 0:
                self._mongo.companies.update_one(
                    {"_id": cid},
                    {"$set": {"icp_fit_score": c_score}},
                    upsert=False,
                )

            for p in persons_by_company.get(cid, []):
                pid = str(p.get("id") or p.get("_id") or "")
                if not pid:
                    continue
                p_score = score_person(p, plan)
                total = combined_score(c_score, p_score)

                # persist person score
                res2 = self._mongo.persons.update_one({"id": pid}, {"$set": {"icp_poc_score": p_score}}, upsert=False)
                if res2.matched_count == 0:
                    self._mongo.persons.update_one(
                        {"_id": pid},
                        {"$set": {"icp_poc_score": p_score}},
                        upsert=False,
                    )

                if total >= min_score:
                    prospects.append(Prospect(company_id=cid, poc_id=pid, score=total))

        prospects.sort(key=lambda x: x.score, reverse=True)

        ranked = [
            {"company_id": p.company_id, "poc_id": p.poc_id, "score": round(p.score, 6)}
            for p in prospects
        ]
        return {"campaign_id": campaign_id, "ranked_prospects": ranked}

