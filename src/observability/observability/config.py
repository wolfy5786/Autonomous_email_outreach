from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Reads from env. Field names map to upper-case env vars via pydantic-settings.

    Aligns with the rest of the system: ``MONGO_URI`` + ``MONGO_DB_NAME``
    (same convention as ``shared.models.db.init_db``).
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "email_outreach"

    log_level: str = "INFO"
    health_port: int = 8090
    page_size: int = 100


settings = Settings()
