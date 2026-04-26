"""Runtime configuration for the sourcing service skeleton."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class SourcingConfig:
    service_name: str = "sourcing-service"
    broker_type: str = "noop"
    sourcing_requested_topic: str = "sourcing.requested"
    sourcing_completed_topic: str = "sourcing.completed"
    sourcing_partial_topic: str = "sourcing.partial"
    log_level: str = "INFO"


def load_config() -> SourcingConfig:
    """Load config from environment with safe defaults."""
    return SourcingConfig(
        service_name=os.getenv("SERVICE_NAME", "sourcing-service"),
        broker_type=os.getenv("BROKER_TYPE", "noop"),
        sourcing_requested_topic=os.getenv(
            "TOPIC_SOURCING_REQUESTED", "sourcing.requested"
        ),
        sourcing_completed_topic=os.getenv(
            "TOPIC_SOURCING_COMPLETED", "sourcing.completed"
        ),
        sourcing_partial_topic=os.getenv("TOPIC_SOURCING_PARTIAL", "sourcing.partial"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )

