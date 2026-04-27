"""
Sourcing service: consumes `sourcing.requested` jobs from RabbitMQ (stub: log only).
"""

from __future__ import annotations

import json
import logging
import signal
import sys
from typing import Any

from messaging.broker_factory import create_broker
from messaging.broker_interface import BrokerInterface

QUEUE_SOURCING_REQUESTED = "sourcing.requested"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("sourcing")


def _handle_message(body: bytes) -> None:
    """Stub processing: parse JSON if possible and log."""
    try:
        payload: Any = json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("Received non-JSON message (logging raw): %r", body[:500])
        return

    job_id = payload.get("job_id") if isinstance(payload, dict) else None
    logger.info(
        "Stub process sourcing job job_id=%s payload=%s",
        job_id,
        payload,
    )


def main() -> None:
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
        broker.close()


if __name__ == "__main__":
    main()
