"""
Sourcing service: consumes ``sourcing.requested`` from RabbitMQ (Docker) and runs the pipeline.
"""

from __future__ import annotations

import asyncio
import signal
import sys

import structlog

from config import settings
from logging_setup import configure_logging
from pipeline import SourcingPipeline
from shared.models.db import init_db
from subscriber import SourcingAMQPConsumer, _safe_broker_host

log = structlog.get_logger(__name__)


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()

    def _set_stop() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _set_stop)
        except NotImplementedError:
            # Windows
            signal.signal(sig, lambda *_a, **_k: stop_event.set())


async def _run() -> None:
    configure_logging(settings.log_level)
    log.info(
        "sourcing service starting",
        module=__name__,
        queue=settings.sourcing_requested_queue,
        broker_host=_safe_broker_host(settings.rabbitmq_url),
    )

    mongo_client = None
    pipeline = SourcingPipeline()
    consumer = SourcingAMQPConsumer(settings, pipeline)
    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event)

    try:
        mongo_client, database = await init_db()
        log.info("mongo initialized", module=__name__, db_name=database.name)

        await consumer.connect()
        await consumer.start_consumer()
        log.info(
            "sourcing service ready",
            module=__name__,
            queue=settings.sourcing_requested_queue,
        )
        await stop_event.wait()
    finally:
        log.info("sourcing service shutting down", module=__name__)
        try:
            await consumer.disconnect()
        except Exception:
            log.error("sourcing service consumer disconnect failed", module=__name__, exc_info=True)
        finally:
            if mongo_client is not None:
                try:
                    mongo_client.close()
                except Exception:
                    log.error("mongo client close failed", module=__name__, exc_info=True)
                else:
                    log.info("mongo client closed", module=__name__)


def main() -> None:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
