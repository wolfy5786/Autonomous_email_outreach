"""Environment-backed settings for the sourcing AMQP consumer."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    rabbitmq_url: str = Field(default="amqp://guest:guest@localhost:5672/")
    rabbit_prefetch: int = 10
    log_level: str = "INFO"
    sourcing_requested_queue: str = "sourcing.requested"


settings = Settings()
