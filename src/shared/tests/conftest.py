"""Test setup for the ``shared`` package.

* Adds ``src/`` to :data:`sys.path` so ``from shared.observability import ...``
  resolves when pytest is invoked from this directory.
* Initialises Beanie with the ``TraceEvent`` model before every test, so any
  test that constructs a ``TraceEvent`` (directly or via ``make_event``) doesn't
  hit ``CollectionWasNotInitialized``. Tests that need the *other* document
  models override this with their own ``db`` fixture.
"""

import sys
from pathlib import Path

import pytest_asyncio
from beanie import init_beanie
from mongomock_motor import AsyncMongoMockClient

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "src"))


@pytest_asyncio.fixture(autouse=True)
async def _init_beanie_for_trace_event():
    from shared.models import TraceEvent

    client = AsyncMongoMockClient()
    await init_beanie(database=client["test_db"], document_models=[TraceEvent])
