"""Read-only access to the ``trace_events`` collection for the observability UI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from shared.models import TraceEvent


@dataclass(frozen=True)
class CampaignSummary:
    """One row on the campaigns list page."""

    campaign_id: str
    first_seen: datetime
    last_seen: datetime
    event_count: int
    services: list[str]


class TraceRepository:
    """Aggregates over ``trace_events`` to power the observability dashboard.

    Construct with the Motor database returned by :func:`shared.models.db.init_db`
    so Beanie is already initialised on the same client.
    """

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._db = db
        self._collection = db[TraceEvent.Settings.name]

    async def list_campaigns(self, limit: int = 100) -> list[CampaignSummary]:
        """Return campaigns ordered by most-recent activity descending."""
        pipeline = [
            {"$match": {"campaign_id": {"$ne": None}}},
            {
                "$group": {
                    "_id": "$campaign_id",
                    "first_seen": {"$min": "$timestamp"},
                    "last_seen": {"$max": "$timestamp"},
                    "event_count": {"$sum": 1},
                    "services": {"$addToSet": "$service"},
                }
            },
            {"$sort": {"last_seen": -1}},
            {"$limit": limit},
        ]
        rows: list[CampaignSummary] = []
        async for doc in self._collection.aggregate(pipeline):
            rows.append(
                CampaignSummary(
                    campaign_id=doc["_id"],
                    first_seen=doc["first_seen"],
                    last_seen=doc["last_seen"],
                    event_count=doc["event_count"],
                    services=sorted(doc["services"]),
                )
            )
        return rows

    async def get_timeline(self, campaign_id: str) -> list[TraceEvent]:
        """Return all trace events for ``campaign_id`` ordered by timestamp ascending."""
        events = (
            await TraceEvent.find(TraceEvent.campaign_id == campaign_id)
            .sort("+timestamp")
            .to_list()
        )
        return events
