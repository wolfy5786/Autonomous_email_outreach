from __future__ import annotations

import logging
import structlog


def configure_logging(service: str = "prospecting", level: str = "info") -> None:
    level = level.upper()
    logging.basicConfig(format="%(message)s", level=getattr(logging, level))

    for noisy in ("httpx", "httpcore", "pika", "pymongo", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    lg = structlog.get_logger(name or "prospecting")
    return lg.bind(service="prospecting")
