"""Environment-backed settings for the sourcing AMQP consumer."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Broker queue declared in ``src/local_infrastructure/rabbit_mq/definitions.json`` (ingress only).
SOURCING_CONSUMER_QUEUE = "sourcing.requested"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    rabbitmq_url: str = Field(default="amqp://guest:guest@localhost:5672/")
    rabbit_prefetch: int = 10
    log_level: str = "INFO"
    events_exchange: str = "email_outreach.events"
    # Routing keys bound in ``src/local_infrastructure/rabbit_mq/definitions.json``.
    sourcing_completed_routing_key: str = "sourcing.completed"
    prospecting_requested_routing_key: str = "prospecting.requested"

    # --- Enrichment (see design_docs/enrichment_redesign.md) ---
    serpapi_api_key: str | None = None
    enrichment_http_timeout_s: float = 30.0
    enrichment_llm_model: str = "gemini/gemini-1.5-pro"
    enrichment_llm_temperature: float = 0.0
    enrichment_llm_max_tokens: int = 1024
    enrichment_llm_timeout_seconds: int = 60
    enrichment_llm_max_retries: int = 3
    # Hard cap on the page-markdown chunk passed to the LLM.
    enrichment_llm_max_chars: int = 20000


settings = Settings()
