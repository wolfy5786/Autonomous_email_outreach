"""
Sourcing service: consumes ``sourcing.requested`` jobs from RabbitMQ and runs the pipeline slice.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from typing import Any

from messaging.broker_factory import create_broker
from messaging.broker_interface import BrokerInterface
from motor.motor_asyncio import AsyncIOMotorClient
from pipeline import SourcingPipeline
from shared.models.db import init_db

QUEUE_SOURCING_REQUESTED = "sourcing.requested"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("sourcing")


def main() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    mongo_client: AsyncIOMotorClient | None = None

    async def _startup_db() -> None:
        nonlocal mongo_client
        client, database = await init_db()
        mongo_client = client
        logger.info("stage=mongo_initialized db_name=%s", database.name)

    loop.run_until_complete(_startup_db())

    pipeline = SourcingPipeline()

    def _handle_message(body: bytes) -> None:
        loop.run_until_complete(pipeline.run(body))

    broker: BrokerInterface = create_broker()

    def _shutdown(_signum: int, _frame: Any) -> None:
        logger.info("Shutdown signal received; stopping consumer...")
        broker.request_stop()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    broker.connect()
    try:
        broker.subscribe(QUEUE_SOURCING_REQUESTED, _handle_message)
    finally:
        if mongo_client is not None:
            mongo_client.close()
            logger.info("stage=mongo_client_closed")
        loop.close()
        broker.close()


if __name__ == "__main__":
    main()
