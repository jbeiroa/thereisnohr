from __future__ import annotations

import importlib
import os
from typing import Generator
from unittest.mock import MagicMock

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from src.extract.types import CandidateSignals
from src.llm.types import LLMCallMetadata, LLMUsage


@pytest.fixture(scope="session", autouse=True)
def mock_default_llm_client() -> Generator[None, None, None]:
    """Globally mocks build_default_llm_client to return a FakeLLM instance."""
    import src.llm.factory as llm_factory
    import src.ingest.service as ingest_service

    class FakeLLM:
        def generate_structured_with_meta(self, prompt, schema, model_alias, **kwargs):
            if schema == CandidateSignals:
                result = CandidateSignals(skills=["Python"])
            else:
                # Use a more predictable mock for other schemas
                result = MagicMock(spec=schema)
            meta = LLMCallMetadata(
                model_alias=model_alias,
                selected_model="fake-model",
                usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            )
            return result, meta

        def embed_with_meta(self, texts, embedding_model_alias):
            vectors = [[0.1] * 1536 for _ in texts]
            meta = LLMCallMetadata(
                model_alias=embedding_model_alias,
                selected_model="fake-embedding-model",
                usage=LLMUsage(estimated_cost_usd=0.0001),
            )
            return vectors, meta

        def embed(self, texts, embedding_model_alias):
            vectors, _ = self.embed_with_meta(texts, embedding_model_alias)
            return vectors

        def generate_structured(self, prompt, schema, model_alias, **kwargs):
            result, _ = self.generate_structured_with_meta(prompt, schema, model_alias, **kwargs)
            return result

    fake_client = FakeLLM()
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(llm_factory, "build_default_llm_client", lambda: fake_client)
        # Also patch where it might have been imported already
        if hasattr(ingest_service, "build_default_llm_client"):
            mp.setattr(ingest_service, "build_default_llm_client", lambda: fake_client)
        
        yield


pytest.importorskip("testcontainers.postgres")
pytest.importorskip("docker")
from docker.errors import DockerException  # noqa: E402
from testcontainers.postgres import PostgresContainer  # noqa: E402

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
