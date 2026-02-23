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


@pytest.fixture(scope="session")
def integration_db_url() -> Generator[str, None, None]:
    try:
        container = PostgresContainer("postgres:16")
    except DockerException as exc:
        pytest.skip(f"Docker is unavailable for integration tests: {exc}")

    try:
        postgres_ctx = container.__enter__()
    except DockerException as exc:
        pytest.skip(f"Docker is unavailable for integration tests: {exc}")

    try:
        postgres = postgres_ctx
        db_url = postgres.get_connection_url().replace("postgresql://", "postgresql+psycopg://")

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
