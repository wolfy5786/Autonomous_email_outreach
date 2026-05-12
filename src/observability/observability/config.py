from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "email_outreach"

    log_level: str = "INFO"
    health_port: int = 8090
    page_size: int = 100


settings = Settings()
