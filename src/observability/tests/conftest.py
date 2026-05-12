"""Test setup for the observability service.

Adds the repo's ``src/`` directory to ``sys.path`` so ``from shared.models ...``
and ``from observability...`` both resolve when pytest runs from this folder.
"""

import sys
from pathlib import Path

import pytest_asyncio
from beanie import init_beanie
from mongomock_motor import AsyncMongoMockClient

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT / "src" / "observability"))


@pytest_asyncio.fixture
async def mock_db():
    """Fresh in-memory Mongo + Beanie initialised on the shared models we read."""
    from shared.models import TraceEvent

    client = AsyncMongoMockClient()
    database = client["test_db"]
    await init_beanie(database=database, document_models=[TraceEvent])
    return database
