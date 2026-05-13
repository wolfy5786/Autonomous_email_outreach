from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Broker
    broker_type: str = "rabbitmq"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    rabbit_prefetch: int = 5

    # Mongo
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "email_outreach"

    # Queues
    messaging_requested_queue: str = "messaging.requested"
    draft_written_queue: str = "draft.written"
    draft_failed_queue: str = "draft.failed"

    # LLM
    llm_model: str = "gemini-2.5-flash"
    llm_temperature: float = 0.4
    llm_max_tokens: int = 1024
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 3

    # Email provider
    email_provider: str = "stub"          # stub | gmail
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    # Per-campaign tokens read at runtime via:
    #   GMAIL_REFRESH_TOKEN_<credentials_ref>
    #   GMAIL_USER_EMAIL_<credentials_ref>

    # Runtime
    health_port: int = 8081
    log_level: str = "INFO"
    graceful_shutdown_seconds: int = 30


settings = Settings()
