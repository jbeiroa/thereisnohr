from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "thereisnohr"
    environment: str = "dev"
    log_level: str = "INFO"

    data_dir: Path = Path("./data")
    model_aliases_path: Path = Path("./config/model_aliases.yaml")

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5433/thereisnohr_stage1"
    )

    embedding_model_alias: str = "embedding_default"
    summarizer_model_alias: str = "summarizer_default"
    extractor_model_alias: str = "extractor_default"
    explainer_model_alias: str = "explainer_default"

    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 2
    ingest_flow_metrics_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
