"""Logging setup for the sourcing service skeleton."""

import logging


def configure_logging(log_level: str) -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format=(
            "%(asctime)s | %(levelname)s | %(name)s | "
            "request_id=%(request_id)s campaign_id=%(campaign_id)s | %(message)s"
        ),
    )
    return logging.getLogger("sourcing")


class RequestContextAdapter(logging.LoggerAdapter):
    """Inject request and campaign identifiers into every log entry."""

    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        merged_extra = {
            "request_id": extra.get("request_id", "-"),
            "campaign_id": extra.get("campaign_id", "-"),
        }
        kwargs["extra"] = merged_extra
        return msg, kwargs

