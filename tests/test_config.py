from src.core.config import Settings


def test_settings_defaults() -> None:
    settings = Settings()
    assert settings.app_name == "thereisnohr"
    assert settings.database_url.startswith("postgresql+psycopg://")
