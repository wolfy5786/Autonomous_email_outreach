"""Sourcing service entry point."""
import asyncio
import signal
import sys
from .config import config
from .handlers import SourcingHandler
from .source_map import get_enabled_sources
from .logging_setup import pipeline_logger as logger


async def main() -> None:
    logger.info("Starting sourcing service...")
    logger.info(f"RabbitMQ: {config.rabbitmq_url}")
    logger.info(f"MongoDB: {config.mongo_uri}")
    logger.info(f"Enabled sources: {get_enabled_sources()}")
    logger.info(f"Rate limit: {config.api_calls_per_second} req/s (burst: {config.api_burst_size})")

    handler = SourcingHandler()

    # In production this connects to RabbitMQ and starts consuming
    # For now, log readiness
    logger.info("Sourcing service ready. Waiting for sourcing.requested events...")

    # Keep alive
    stop = asyncio.Event()

    def handle_signal(sig: signal.Signals) -> None:
        logger.info(f"Received {sig.name}, shutting down...")
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal, sig)

    await stop.wait()
    logger.info("Sourcing service stopped.")


def entrypoint() -> None:
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    entrypoint()
