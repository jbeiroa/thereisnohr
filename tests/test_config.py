from src.core.config import Settings


def test_settings_defaults() -> None:
    settings = Settings()
    assert settings.app_name == "thereisnohr"
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.model_aliases_path.as_posix().endswith("config/model_aliases.yaml")
    assert settings.llm_max_retries == 2
