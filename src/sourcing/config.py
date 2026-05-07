"""Sourcing service configuration."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SourcingConfig:
    rabbitmq_url: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672")
    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://localhost:27017/outreach")
    exchange: str = os.getenv("EXCHANGE_NAME", "outreach.events")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Rate limiting
    api_calls_per_second: float = float(os.getenv("API_RATE_LIMIT", "2.0"))
    api_burst_size: int = int(os.getenv("API_BURST_SIZE", "5"))

    # Retry
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    retry_base_delay: float = float(os.getenv("RETRY_BASE_DELAY", "2.0"))

    # Discovery sources
    enable_yc: bool = os.getenv("ENABLE_YC", "true").lower() == "true"
    enable_hacker_news: bool = os.getenv("ENABLE_HN", "true").lower() == "true"
    enable_product_hunt: bool = os.getenv("ENABLE_PH", "false").lower() == "true"
    enable_opencorporates: bool = os.getenv("ENABLE_OPENCORP", "false").lower() == "true"

    # Cache
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL", "86400"))

    @classmethod
    def from_env(cls) -> "SourcingConfig":
        return cls()


config = SourcingConfig.from_env()
