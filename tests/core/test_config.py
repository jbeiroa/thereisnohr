import pytest

from src.core.config import Settings


def test_settings_defaults() -> None:
    settings = Settings()
    assert settings.app_name == "thereisnohr"
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.model_aliases_path.as_posix().endswith("config/model_aliases.yaml")
    assert settings.llm_max_retries == 2


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that environment variables override default values."""
    monkeypatch.setenv("APP_NAME", "custom_ats")
    monkeypatch.setenv("ENVIRONMENT", "prod")

    settings = Settings()

    assert settings.app_name == "custom_ats"
    assert settings.environment == "prod"
