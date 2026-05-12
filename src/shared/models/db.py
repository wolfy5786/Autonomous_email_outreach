from __future__ import annotations

import os

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from shared.models.company import CompanyRecord
from shared.models.email_draft import EmailDraft
from shared.models.hint import Hint
from shared.models.plan import PlanRecord

MONGO_URI_ENV = "MONGO_URI"
MONGO_DB_ENV = "MONGO_DB_NAME"
DEFAULT_MONGO_URI = "mongodb://localhost:27017"
DEFAULT_DB_NAME = "email_outreach"


async def init_db(
    connection_string: str | None = None,
    database_name: str | None = None,
) -> tuple[AsyncIOMotorClient, AsyncIOMotorDatabase]:
    """
    Create Motor client, initialize Beanie on the given database, and return ``(client, database)``.

    Environment:
    * ``MONGO_URI`` (default: ``mongodb://localhost:27017``)
    * ``MONGO_DB_NAME`` (default: ``email_outreach``)
    """
    uri = connection_string or os.environ.get(MONGO_URI_ENV, DEFAULT_MONGO_URI)
    db_name = database_name or os.environ.get(MONGO_DB_ENV, DEFAULT_DB_NAME)
    client = AsyncIOMotorClient(uri)
    database = client[db_name]
    await init_beanie(
        database=database,
        document_models=[CompanyRecord, Hint, PlanRecord, EmailDraft],
    )
    return client, database
