from __future__ import annotations

import importlib
import os
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

pytest.importorskip("testcontainers.postgres")
pytest.importorskip("docker")
from docker.errors import DockerException
from testcontainers.postgres import PostgresContainer

DEFAULT_INTEGRATION_POSTGRES_IMAGE = "pgvector/pgvector:pg16"


def _normalize_postgres_url(raw_url: str) -> str:
    """Normalizes testcontainer URLs to the psycopg3 SQLAlchemy dialect."""
    if raw_url.startswith("postgresql+psycopg2://"):
        return raw_url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    if raw_url.startswith("postgresql://"):
        return raw_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw_url


@pytest.fixture(scope="session")
def integration_db_url() -> Generator[str, None, None]:
    image = os.getenv("INTEGRATION_POSTGRES_IMAGE", DEFAULT_INTEGRATION_POSTGRES_IMAGE)
    try:
        container = PostgresContainer(image)
    except DockerException as exc:
        pytest.skip(f"Docker is unavailable for integration tests: {exc}")

    try:
        postgres_ctx = container.__enter__()
    except DockerException as exc:
        pytest.skip(f"Docker is unavailable for integration tests: {exc}")

    try:
        postgres = postgres_ctx
        db_url = _normalize_postgres_url(postgres.get_connection_url())

        os.environ["DATABASE_URL"] = db_url

        import src.core.config as core_config

        core_config.get_settings.cache_clear()

        import src.storage.db as storage_db

        importlib.reload(storage_db)

        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        command.upgrade(alembic_cfg, "head")

        yield db_url
    finally:
        try:
            container.__exit__(None, None, None)
        except DockerException:
            pass


@pytest.fixture(scope="function")
def db_session(integration_db_url):
    import src.core.config as core_config

    core_config.get_settings.cache_clear()

    import src.storage.db as storage_db

    importlib.reload(storage_db)
    session = storage_db.get_session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function", autouse=True)
def truncate_tables(integration_db_url):
    import src.core.config as core_config

    core_config.get_settings.cache_clear()

    import src.storage.db as storage_db

    importlib.reload(storage_db)
    session = storage_db.get_session()
    try:
        session.execute(
            text(
                """
                TRUNCATE TABLE
                    matches,
                    embeddings,
                    embedding_models,
                    resume_sections,
                    resumes,
                    candidates,
                    job_postings
                RESTART IDENTITY CASCADE
                """
            )
        )
        session.commit()
        yield
    finally:
        session.close()
