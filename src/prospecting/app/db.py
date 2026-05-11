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

    def get_plan(self, campaign_id: str) -> dict[str, Any] | None:
        campaign = self.get_campaign(campaign_id)
        campaign_plan_id = campaign.get("plan_id") if campaign else None
        if campaign_plan_id:
            return self.plans.find_one({"id": campaign_plan_id}) or self.plans.find_one({"_id": campaign_plan_id})
        return self.plans.find_one({"campaign_id": campaign_id})

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

    def update_company_score(self, company_id: str, campaign_id: str, score: float, scoring_version: str) -> None:
        self.companies.update_one(
            {"$or": [{"id": company_id}, {"_id": company_id}]},
            {"$set": {"icp_fit_score": score, "scoring_version": scoring_version}},
            upsert=False,
        )

    def update_person_score(self, person_id: str, campaign_id: str, score: float, scoring_version: str) -> None:
        self.persons.update_one(
            {"$or": [{"id": person_id}, {"_id": person_id}]},
            {"$set": {"icp_poc_score": score, "scoring_version": scoring_version}},
            upsert=False,
        )

    def update_person_email_verified(self, person_id: str, verified: bool) -> None:
        self.persons.update_one(
            {"$or": [{"id": person_id}, {"_id": person_id}]},
            {"$set": {"email_verified": verified}},
            upsert=False,
        )

