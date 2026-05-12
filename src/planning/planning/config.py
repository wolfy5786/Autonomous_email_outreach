from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Broker
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    rabbitmq_exchange: str = Field(default="email_outreach.events")
    rabbit_prefetch: int = 10

    # Mongo
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "email_outreach"

    # Queues
    plan_requested_queue: str = "plan.requested"
    plan_ready_queue: str = "plan.ready"
    sourcing_requested_queue: str = "sourcing.requested"

    # LLM
    llm_model: str = "gemini/gemini-1.5-pro"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 3

    # Runtime
    health_port: int = 8080
    log_level: str = "INFO"
    graceful_shutdown_seconds: int = 30


settings = Settings()
