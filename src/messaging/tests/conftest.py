import pytest_asyncio
from beanie import init_beanie
from mongomock_motor import AsyncMongoMockClient

from messaging.repository import MessagingRepository
from shared.models import CompanyRecord, EmailDraft, Hint, PlanRecord


@pytest_asyncio.fixture
async def repo() -> MessagingRepository:
    """Fresh in-memory Mongo per test, with Beanie initialized so EmailDraft
    instances can be constructed/validated (matches production startup)."""
    client = AsyncMongoMockClient()
    db = client["test_db"]
    await init_beanie(
        database=db,
        document_models=[CompanyRecord, Hint, PlanRecord, EmailDraft],
    )
    return MessagingRepository(db)
