from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    rabbitmq_url: str = Field(default="amqp://guest:guest@localhost:5672/%2F", alias="RABBITMQ_URL")
    rabbitmq_exchange: str = Field(default="email_outreach.events", alias="RABBITMQ_EXCHANGE")
    rabbitmq_prefetch: int = Field(default=10, alias="RABBITMQ_PREFETCH")

    mongodb_uri: str = Field(alias="MONGODB_URI")
    mongodb_db: str = Field(default="email_outreach", alias="MONGODB_DB")

    default_min_icp_score: float = Field(default=0.0, alias="DEFAULT_MIN_ICP_SCORE")

    http_host: str = Field(default="0.0.0.0", alias="HTTP_HOST")
    http_port: int = Field(default=8004, alias="HTTP_PORT")

