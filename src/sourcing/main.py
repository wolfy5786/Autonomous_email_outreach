"""
Sourcing service: consumes ``sourcing.requested`` jobs from RabbitMQ and runs the pipeline slice.
"""

from __future__ import annotations

import asyncio
import json
import signal
import uuid
from typing import Any

import structlog
from messaging.broker_factory import create_broker
from messaging.broker_interface import BrokerInterface
from motor.motor_asyncio import AsyncIOMotorClient
from pipeline import SourcingPipeline
from shared.models.db import init_db
from shared.observability import (
    MongoTraceSink,
    configure_logging,
    set_trace_sink,
    trace_operation,
)

QUEUE_SOURCING_REQUESTED = "sourcing.requested"

configure_logging(service="sourcing")
logger = structlog.get_logger("sourcing")


def main() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    mongo_client: AsyncIOMotorClient | None = None

    async def _startup_db() -> None:
        nonlocal mongo_client
        client, database = await init_db()
        mongo_client = client
        logger.info("mongo_initialized", db_name=database.name)
        set_trace_sink(MongoTraceSink())
        logger.info("trace_sink_activated", sink="MongoTraceSink")

    loop.run_until_complete(_startup_db())

    pipeline = SourcingPipeline()

    def _handle_message(body: bytes) -> None:
        """Sync entry point from the (blocking) sourcing broker.

        Extracts trace_id / campaign_id from the message so subsequent logs and any
        downstream publishes inherit them, then wraps the async pipeline in a
        ``trace_operation`` so the consume cycle appears on the campaign timeline.
        """

        async def _run() -> None:
            trace_id: str = str(uuid.uuid4())
            campaign_id: str | None = None
            try:
                raw = json.loads(body.decode("utf-8"))
                if isinstance(raw, dict):
                    trace_id = raw.get("trace_id") or trace_id
                    campaign_id = raw.get("campaign_id")
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass  # pipeline.run logs malformed bodies via its own logger

            async with trace_operation(
                trace_id=trace_id,
                campaign_id=campaign_id,
                service="sourcing",
                event_name="sourcing.requested.consume",
                metadata={"topic": QUEUE_SOURCING_REQUESTED},
            ):
                await pipeline.run(body)

        loop.run_until_complete(_run())

    broker: BrokerInterface = create_broker()

    def _shutdown(_signum: int, _frame: Any) -> None:
        logger.info("shutdown_signal_received")
        broker.request_stop()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    broker.connect()
    try:
        broker.subscribe(QUEUE_SOURCING_REQUESTED, _handle_message)
    finally:
        set_trace_sink(None)
        if mongo_client is not None:
            mongo_client.close()
            logger.info("mongo_client_closed")
        loop.close()
        broker.close()


if __name__ == "__main__":
    main()
