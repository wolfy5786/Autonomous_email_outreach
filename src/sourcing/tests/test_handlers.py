"""Tests for sourcing job execution and non-retryable error mapping."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from handlers import NonRetryableSourcingError, execute_sourcing_pipeline
from pipeline import PlanNotFoundError


@pytest.mark.asyncio
async def test_execute_sourcing_pipeline_wraps_plan_not_found() -> None:
    pipeline = MagicMock()
    inner = PlanNotFoundError("no plan")
    pipeline.run = AsyncMock(side_effect=inner)

    with pytest.raises(NonRetryableSourcingError) as exc_info:
        await execute_sourcing_pipeline(b'{"campaign_id":"c","plan_id":"p"}', pipeline)

    assert exc_info.value.__cause__ is inner
    pipeline.run.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_sourcing_pipeline_wraps_validation_error() -> None:
    pipeline = MagicMock()
    inner = ValidationError.from_exception_data(
        "SourcingRequestedJob",
        [{"type": "missing", "loc": ("campaign_id",), "input": {}}],
    )
    pipeline.run = AsyncMock(side_effect=inner)

    with pytest.raises(NonRetryableSourcingError) as exc_info:
        await execute_sourcing_pipeline(b"{}", pipeline)

    assert exc_info.value.__cause__ is inner


@pytest.mark.asyncio
async def test_execute_sourcing_pipeline_passes_through_success() -> None:
    pipeline = MagicMock()
    pipeline.run = AsyncMock(return_value=None)

    await execute_sourcing_pipeline(b'{"campaign_id":"c","plan_id":"p"}', pipeline)

    pipeline.run.assert_awaited_once()
