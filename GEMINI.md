# Gemini Context: thereisnohr

`thereisnohr` is a provider-agnostic Applicant Tracking System (ATS) designed to ingest resumes, extract candidate signals, and perform semantic retrieval and ranking.

## Project Overview

- **Purpose:** A modular ATS that handles the end-to-end lifecycle of resume processing, from PDF ingestion to AI-driven candidate matching.
- **Core Technologies:**
  - **Language:** Python 3.12+
  - **Dependency Management:** `uv`
  - **Web Framework:** FastAPI
  - **Database:** PostgreSQL with `pgvector` for semantic search.
  - **ORM:** SQLAlchemy 2.0 (Mapped types) with Alembic for migrations.
  - **LLM Integration:** LiteLLM (provider-agnostic) with a custom alias registry.
  - **Orchestration:** Metaflow for data pipelines (e.g., PDF ingestion).
  - **Validation:** Pydantic V2 and `pydantic-settings`.
  - **CLI:** Typer.

## Architecture Map

- `src/core/`: Runtime configuration (`config.py`) and logging.
- `src/api/`: FastAPI application and endpoint definitions.
- `src/storage/`: Database schema (`models.py`), migrations, and Repository pattern implementations.
- `src/llm/`: Abstraction layer for LLM interactions, including a factory for client construction and a model alias registry.
- `src/ingest/`: Resume parsing logic (PDF focus), identity resolution (email/phone/name matching), and Metaflow flows.
- `src/extract/`, `src/retrieval/`, `src/ranking/`: Service boundaries for candidate signal extraction and ranking.
- `alembic/`: Database migration scripts and configuration.
- `notebooks/`: Research and testing notebooks for parsers, LLMs, and repositories.

## Key Commands

All commands should be executed via `uv`.

### Environment & Setup
- **Sync Dependencies:** `uv sync --all-extras --dev`
- **Copy Environment:** `cp .env.example .env` (then update values)

### Development & Execution
- **Run API (Dev):** `uv run uvicorn src.api.app:app --reload`
- **CLI Entrypoint:** `uv run ats --help`
- **Run Migrations:** `uv run alembic upgrade head`
- **Run Ingestion Flow:** `uv run python src/ingest/pdf_ingestion_flow.py run --input-dir data --pattern '*.pdf'`

### Testing & Quality
- **Unit Tests:** `uv run pytest`
- **Integration Tests:** `uv run pytest -m integration` (Requires Docker for Testcontainers)
- **Linting:** `uv run ruff check .`
- **Type Checking:** `uv run mypy .`

## Development Conventions

1. **Configuration:** Use `src/core/config.py` (Pydantic `BaseSettings`). Avoid hardcoding environment variables outside this file.
2. **Database:** Follow the Repository pattern found in `src/storage/repositories.py`. Use SQLAlchemy 2.0 `Mapped` styles for models.
3. **LLM Usage:** Always use `src.llm.factory.build_default_llm_client()` and reference models via aliases defined in `config/model_aliases.yaml`.
4. **Idempotency:** Ingestion uses content-hashing to prevent duplicate resume processing.
5. **Logging:** Use the structured logger from `src.core.logging`.
6. **Testing:** New features must include tests. Integration tests requiring a database should be marked with `@pytest.mark.integration`.
