"""Structured logging for the sourcing service (JSON to stdout)."""

import logging

import structlog


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog + stdlib logging for JSON output to stdout."""
    logging.basicConfig(format="%(message)s", level=level.upper())

    # httpx logs full request URLs (including API keys in query params) at DEBUG
    # level. Cap these loggers so they never emit request details regardless of
    # the service log level.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[level.upper()]
        ),
        cache_logger_on_first_use=True,
    )
