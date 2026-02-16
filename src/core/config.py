from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "thereisnohr"
    environment: str = "dev"
    log_level: str = "INFO"

    data_dir: Path = Path("./data")

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/thereisnohr"
    )

    embedding_model_alias: str = "embedding_default"
    summarizer_model_alias: str = "summarizer_default"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
