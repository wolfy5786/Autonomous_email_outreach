"""Entrypoint for the sourcing service skeleton."""

import asyncio

from .config import load_config
from .logging_config import RequestContextAdapter, configure_logging
from .messaging.broker_factory import create_broker
from .pipeline import SourcingPipeline
from .service import SourcingService


def build_service() -> SourcingService:
    config = load_config()
    root_logger = configure_logging(config.log_level)
    logger = RequestContextAdapter(root_logger, {"request_id": "-", "campaign_id": "-"})

    logger.info("service=sourcing action=bootstrap status=starting")
    broker = create_broker(config.broker_type, logger=logger)
    pipeline = SourcingPipeline(logger=logger)
    return SourcingService(config=config, broker=broker, pipeline=pipeline, logger=logger)


async def run() -> None:
    service = build_service()
    await service.start()


if __name__ == "__main__":
    asyncio.run(run())

