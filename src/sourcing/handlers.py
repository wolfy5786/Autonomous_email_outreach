"""Run sourcing jobs from queue payloads — maps domain failures to permanent errors for DLQ routing."""

from __future__ import annotations

from pydantic import ValidationError

from pipeline import PlanNotFoundError, SourcingPipeline


class NonRetryableSourcingError(Exception):
    """Permanent failure — message must not be requeued (routes to DLQ via x-dead-letter)."""


async def execute_sourcing_pipeline(body: bytes, pipeline: SourcingPipeline) -> None:
    """Execute the pipeline for one message body; wrap non-retryable domain errors."""
    try:
        await pipeline.run(body)
    except PlanNotFoundError as exc:
        raise NonRetryableSourcingError(str(exc)) from exc
    except ValidationError as exc:
        raise NonRetryableSourcingError("invalid sourcing job payload") from exc
