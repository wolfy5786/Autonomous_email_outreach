from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database


@dataclass(frozen=True)
class MongoConfig:
    uri: str
    db_name: str


class Mongo:
    def __init__(self, cfg: MongoConfig):
        self._cfg = cfg
        self._client: MongoClient | None = None
        self._db: Database | None = None

    def connect(self) -> None:
        self._client = MongoClient(self._cfg.uri)
        self._db = self._client[self._cfg.db_name]

    def close(self) -> None:
        if self._client:
            self._client.close()

    @property
    def db(self) -> Database:
        if self._db is None:
            raise RuntimeError("mongo not connected")
        return self._db

    @property
    def campaigns(self) -> Collection:
        return self.db["campaigns"]

    @property
    def plans(self) -> Collection:
        return self.db["plans"]

    @property
    def companies(self) -> Collection:
        return self.db["companies"]

    @property
    def persons(self) -> Collection:
        return self.db["persons"]

    @property
    def processed_events(self) -> Collection:
        return self.db["prospecting_events"]

    def get_plan(self, campaign_id: str) -> dict[str, Any] | None:
        campaign = self.get_campaign(campaign_id)
        campaign_plan_id = campaign.get("plan_id") if campaign else None
        if campaign_plan_id:
            return self.plans.find_one({"id": campaign_plan_id}) or self.plans.find_one({"_id": campaign_plan_id})
        return self.plans.find_one({"campaign_id": campaign_id})

    def is_event_processed(self, event_id: str, campaign_id: str | None = None) -> bool:
        if not event_id:
            return False
        query = {"_id": event_id}
        if campaign_id:
            query["campaign_id"] = campaign_id
        doc = self.processed_events.find_one(query)
        return bool(doc and doc.get("published") is True)

    def mark_event_processed(self, event_id: str, campaign_id: str | None = None, payload: dict | None = None) -> None:
        if not event_id:
            return
        doc = {"_id": event_id, "campaign_id": campaign_id, "published": True, "payload": payload or {}, "published_at": None}
        try:
            from datetime import datetime

            doc["published_at"] = datetime.utcnow().isoformat()
        except Exception:
            doc["published_at"] = None
        self.processed_events.update_one({"_id": event_id}, {"$set": doc}, upsert=True)

    def get_campaign(self, campaign_id: str) -> dict[str, Any] | None:
        return self.campaigns.find_one({"id": campaign_id}) or self.campaigns.find_one({"_id": campaign_id})

    def get_companies(self, company_ids: Iterable[str]) -> list[dict[str, Any]]:
        ids = list(company_ids)
        if not ids:
            return []
        return list(self.companies.find({"id": {"$in": ids}})) or list(self.companies.find({"_id": {"$in": ids}}))

    def get_persons_for_companies(self, company_ids: Iterable[str]) -> list[dict[str, Any]]:
        ids = list(company_ids)
        if not ids:
            return []
        return list(self.persons.find({"company_id": {"$in": ids}}))

    def update_company_score(
        self,
        company_id: str,
        campaign_id: str,
        score: float,
        scoring_version: str,
        scored_at: str | None = None,
        reasons: dict | None = None,
        event_id: str | None = None,
    ) -> None:
        """Persist global and campaign-scoped company scoring information.

        Writes both top-level `icp_fit_score` and a campaign-scoped record under
        `prospecting_scores.<campaign_id>` to avoid cross-campaign overwrite.
        """
        scoped = {
            "icp_fit_score": score,
            "scoring_version": scoring_version,
            "scored_at": scored_at,
            "campaign_id": campaign_id,
            "event_id": event_id,
            "reasons": reasons or {},
        }
        set_fields = {
            "icp_fit_score": score,
            "scoring_version": scoring_version,
            f"prospecting_scores.{campaign_id}": scoped,
        }
        self.companies.update_one(
            {"$or": [{"id": company_id}, {"_id": company_id}]},
            {"$set": set_fields},
            upsert=False,
        )

    def update_person_score(
        self,
        person_id: str,
        campaign_id: str,
        score: float,
        scoring_version: str,
        scored_at: str | None = None,
        reasons: dict | None = None,
        event_id: str | None = None,
    ) -> None:
        """Persist global and campaign-scoped person scoring information."""
        scoped = {
            "icp_poc_score": score,
            "scoring_version": scoring_version,
            "scored_at": scored_at,
            "campaign_id": campaign_id,
            "event_id": event_id,
            "reasons": reasons or {},
        }
        set_fields = {
            "icp_poc_score": score,
            "scoring_version": scoring_version,
            f"prospecting_scores.{campaign_id}": scoped,
        }
        self.persons.update_one(
            {"$or": [{"id": person_id}, {"_id": person_id}]},
            {"$set": set_fields},
            upsert=False,
        )

    def update_person_email_verified(self, person_id: str, verified: bool) -> None:
        self.persons.update_one(
            {"$or": [{"id": person_id}, {"_id": person_id}]},
            {"$set": {"email_verified": verified}},
            upsert=False,
        )

