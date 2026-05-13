"""Tests for the Person-skeleton upsert that runs after linkedin_poc enrichment.

When sourcing's linkedin_poc op extracts a poc_name, the pipeline must also
write a Person doc into the ``persons`` collection so downstream services
(prospecting, messaging) can find a POC by ``company_id``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pipeline import SourcingPipeline
from shared.models.company import CompanyRecord


def _make_company(
    *,
    id_: str = "co-123",
    name: str = "HireArt",
    domain: str = "hireart.com",
    extra: dict | None = None,
) -> CompanyRecord:
    """Build a CompanyRecord fixture without touching the DB.

    Uses ``model_construct`` to bypass Beanie's __init__ hook (which calls
    ``get_motor_collection`` and requires ``init_beanie`` to have run).
    """
    return CompanyRecord.model_construct(
        id=id_,
        name=name,
        domain=domain,
        freshness_timestamp=datetime(2026, 5, 13, tzinfo=timezone.utc),
        extra=extra or {},
        provenance={},
        campaign_ids=[],
    )


@pytest.mark.asyncio
async def test_upsert_person_writes_doc_when_poc_name_present() -> None:
    """Happy path: poc_name + poc_profile_url -> Person upsert with synthesized email."""
    company = _make_company(
        extra={
            "poc_name": "Chris Forbes",
            "poc_profile_url": "https://www.linkedin.com/in/chrisforbeshireart",
        }
    )
    persons_collection = MagicMock()
    persons_collection.update_one = AsyncMock()
    motor_collection = MagicMock()
    motor_collection.database = {"persons": persons_collection}

    pipeline = SourcingPipeline()

    with patch.object(CompanyRecord, "get_motor_collection", return_value=motor_collection):
        await pipeline._upsert_person_from_extra(company)

    persons_collection.update_one.assert_awaited_once()
    call = persons_collection.update_one.await_args
    # Filter is by _id for idempotent upsert.
    assert call.args[0] == {"_id": "co-123-poc-linkedin"}
    # Upsert flag is set.
    assert call.kwargs.get("upsert") is True

    doc = call.args[1]["$set"]
    assert doc["_id"] == "co-123-poc-linkedin"
    assert doc["id"] == "co-123-poc-linkedin"
    assert doc["company_id"] == "co-123"
    assert doc["name"] == "Chris Forbes"
    assert doc["first_name"] == "Chris"
    assert doc["last_name"] == "Forbes"
    assert doc["email"] == "chris.forbes@hireart.com"
    assert doc["email_verified"] is False
    assert doc["linkedin_url"] == "https://www.linkedin.com/in/chrisforbeshireart"
    assert doc["icp_poc_score"] is None
    assert doc["extra"]["source"] == "sourcing.linkedin_poc"


@pytest.mark.asyncio
async def test_upsert_person_skips_when_no_poc_name() -> None:
    """No poc_name in company.extra -> no DB write."""
    company = _make_company(extra={"company_summary": "some summary"})  # no poc_name
    persons_collection = MagicMock()
    persons_collection.update_one = AsyncMock()
    motor_collection = MagicMock()
    motor_collection.database = {"persons": persons_collection}

    pipeline = SourcingPipeline()

    with patch.object(CompanyRecord, "get_motor_collection", return_value=motor_collection):
        await pipeline._upsert_person_from_extra(company)

    persons_collection.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_upsert_person_handles_single_name_token() -> None:
    """Single-token poc_name -> first_name set, last_name None, no email synthesized."""
    company = _make_company(extra={"poc_name": "Cher"})
    persons_collection = MagicMock()
    persons_collection.update_one = AsyncMock()
    motor_collection = MagicMock()
    motor_collection.database = {"persons": persons_collection}

    pipeline = SourcingPipeline()

    with patch.object(CompanyRecord, "get_motor_collection", return_value=motor_collection):
        await pipeline._upsert_person_from_extra(company)

    doc = persons_collection.update_one.await_args.args[1]["$set"]
    assert doc["first_name"] == "Cher"
    assert doc["last_name"] is None
    # Email synthesis requires both first AND last name to be safe.
    assert doc["email"] is None
    assert doc["linkedin_url"] is None  # poc_profile_url absent


@pytest.mark.asyncio
async def test_upsert_person_is_idempotent_id_scheme() -> None:
    """Re-invocation with the same company_id reuses the same _id (upsert in place)."""
    company = _make_company(extra={"poc_name": "Chris Forbes"})
    persons_collection = MagicMock()
    persons_collection.update_one = AsyncMock()
    motor_collection = MagicMock()
    motor_collection.database = {"persons": persons_collection}

    pipeline = SourcingPipeline()

    with patch.object(CompanyRecord, "get_motor_collection", return_value=motor_collection):
        await pipeline._upsert_person_from_extra(company)
        await pipeline._upsert_person_from_extra(company)

    assert persons_collection.update_one.await_count == 2
    first_call = persons_collection.update_one.await_args_list[0]
    second_call = persons_collection.update_one.await_args_list[1]
    assert first_call.args[0] == second_call.args[0] == {"_id": "co-123-poc-linkedin"}
