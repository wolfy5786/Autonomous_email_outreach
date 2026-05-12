import logging
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from .schemas import CampaignRecord, PlanRecord

log = logging.getLogger(__name__)


class PlanRepository:
    """Mongo access for the Planning service.

    Convention: we store the business `id` string as Mongo `_id` (no ObjectId).
    This is consistent across services so cross-collection lookups stay cheap.
    """

    def __init__(self, mongo_url: str, db_name: str) -> None:
        self._client: AsyncIOMotorClient[dict[str, Any]] = AsyncIOMotorClient(mongo_url)
        self._db: AsyncIOMotorDatabase[dict[str, Any]] = self._client[db_name]

    @property
    def db(self) -> AsyncIOMotorDatabase[dict[str, Any]]:
        return self._db

    async def bootstrap_indexes(self) -> None:
        """Idempotent — safe to call every startup."""
        await self._db["plans"].create_index("campaign_id", unique=True, name="uniq_campaign_id")
        await self._db["plans"].create_index("id", unique=True, name="uniq_plan_id")
        log.info("mongo indexes bootstrapped")

    async def ping(self) -> bool:
        try:
            await self._db.command("ping")
            return True
        except Exception:
            log.exception("mongo ping failed")
            return False

    async def get_campaign(self, campaign_id: str) -> CampaignRecord | None:
        # Three lookup paths, in priority order:
        # 1. _id == campaign_id  → planning's own seed_campaign.py convention
        # 2. id == campaign_id   → some legacy seed scripts
        # 3. campaign_id == ...  → the TS orchestrator (mongoose) — it stores the
        #    business id in a `campaign_id` field and leaves _id as an ObjectId.
        doc = await self._db["campaigns"].find_one({"_id": campaign_id})
        if doc is None:
            doc = await self._db["campaigns"].find_one({"id": campaign_id})
        if doc is None:
            doc = await self._db["campaigns"].find_one({"campaign_id": campaign_id})
        if doc is None:
            return None
        # Normalise — schema expects `id`. Prefer the explicit campaign_id field;
        # fall back to _id only if it's already a string.
        if "id" not in doc:
            doc["id"] = doc.get("campaign_id") or str(doc.get("_id"))
        return CampaignRecord.model_validate(doc)

    async def find_existing_plan_id(self, campaign_id: str) -> str | None:
        doc = await self._db["plans"].find_one({"campaign_id": campaign_id}, {"id": 1, "_id": 0})
        return doc["id"] if doc else None

    async def save_plan(self, plan: PlanRecord) -> None:
        """Insert the plan. Raises DuplicateKeyError if campaign already has one."""
        doc = plan.model_dump(mode="json")  # UUID -> str, datetime -> iso str
        doc["_id"] = doc["id"]
        try:
            await self._db["plans"].insert_one(doc)
        except DuplicateKeyError:
            # Re-raise so the handler can recover by republishing the existing id.
            raise

    async def attach_plan_to_campaign(self, campaign_id: str, plan_id: str) -> None:
        await self._db["campaigns"].update_one(
            {"_id": campaign_id},
            {"$set": {"plan_id": plan_id}},
        )

    async def close(self) -> None:
        self._client.close()
