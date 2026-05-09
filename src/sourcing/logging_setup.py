"""Configure structured logging for the sourcing service."""
from src.shared.observability.logger import get_logger

# Module-level loggers for each sourcing component
pipeline_logger = get_logger("sourcing.pipeline")
discovery_logger = get_logger("sourcing.discovery")
enrichment_logger = get_logger("sourcing.enrichment")
validation_logger = get_logger("sourcing.validation")
subscriber_logger = get_logger("sourcing.subscriber")
