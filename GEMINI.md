# Gemini Context: thereisnohr

`thereisnohr` is a provider-agnostic Applicant Tracking System (ATS) designed to ingest resumes, extract candidate signals, and perform semantic retrieval and ranking.

## Project Overview
A modular ATS that handles the end-to-end lifecycle of resume processing, from PDF ingestion to AI-driven candidate matching.

- **Core Technologies:** Python 3.12+, `uv`, FastAPI, PostgreSQL + `pgvector`, SQLAlchemy 2.0 (Mapped types), Alembic, LiteLLM, Metaflow, Pydantic V2, and Typer.
- **Capabilities:** Typed settings, structured logging, SQLAlchemy repositories, provider-agnostic LLM client with alias registry, PDF parsing, identity resolution, deduplication by content hash, and Metaflow-orchestrated ingestion pipelines.

## Source of Truth
When sources disagree, prefer, in order:
1. Current code under `src/` and runtime behavior.
2. Tests under `tests/`.
3. Documentation under `docs/`.
4. Plans under `.plans/`.

## Architecture Map & Module Responsibilities
- `src/core/`: Runtime configuration (`config.py`) and structured logging with run IDs (`logging.py`).
- `src/storage/`: Database schema (`models.py`), migrations, and Repository pattern implementations.
- `src/llm/`: Provider-agnostic client, model alias registry, error handling, and factory.
- `src/ingest/`: PDF parsing logic, identity resolution, model fallback, ingestion service, and Metaflow orchestration.
- `src/extract/`: Extraction service boundary and types (candidate signal extraction).
- `src/retrieval/`: Retrieval service boundary (semantic search).
- `src/ranking/`: Ranking service boundary, types, and workflow (candidate hybrid ranking).
- `src/api/`: FastAPI application (`app.py`) with service endpoints.
- `src/cli.py`: Typer CLI entrypoint for `ingest`, `ingest-job`, `index`, `rank`, etc.
- `alembic/`: Database migration scripts and configuration.
- `config/`: Model alias configuration (`model_aliases.yaml`).
- `scripts/`: Maintenance and backfill utilities.
- `tests/`: Unit and integration tests (using Testcontainers for Postgres).
- `docs/`: Architecture and development guides.
- `thereisnohr/`: **Legacy pipeline** (historical reference only; do not extend).

## Key Commands
All commands should be executed via `uv`.

### Environment & Setup
- **Sync Dependencies:** `uv sync --all-extras --dev`
- **Setup Environment:** `cp .env.example .env` (then update values)

### Development & Execution
- **Run API (Dev):** `uv run uvicorn src.api.app:app --reload`
- **CLI Entrypoint:** `uv run ats --help`
- **Run Ingestion Flow:** `uv run python src/ingest/pdf_ingestion_flow.py run --input-dir data --pattern '*.pdf'`
- **Ingest Job Description:** `uv run ats ingest-job <path> --title "Job Title"`
- **Rank Candidates:** `uv run ats rank <job_id> --top-k 5`

### Database & Migrations
- **Run Migrations:** `uv run alembic upgrade head`
- **Downgrade Migration:** `uv run alembic downgrade -1`
- **View Migration SQL:** `uv run alembic upgrade head --sql`

### Testing & Quality
- **Unit Tests:** `uv run pytest -q`
- **Integration Tests:** `uv run pytest -q -m integration` (Requires Docker)
- **Linting:** `uv run ruff check .`
- **Type Checking:** `uv run mypy .`

## Development Conventions & Expectations
1. **Configuration:** Use `src/core/config.py` (Pydantic `BaseSettings`). Avoid hardcoding environment variables.
2. **Database:** Follow the Repository pattern in `src/storage/repositories.py`. Use SQLAlchemy 2.0 `Mapped` styles.
3. **LLM Usage:** Always use `src.llm.factory.build_default_llm_client()` and reference models via aliases in `config/model_aliases.yaml`.
4. **Idempotency:** Ingestion uses content-hashing to prevent duplicate resume processing.
5. **Logging:** Use the structured logger from `src.core.logging`.
6. **Testing:** New features must include tests. Integration tests requiring a database should be marked with `@pytest.mark.integration`.
7. **Refactoring:** Prefer modifying `src/` modules; avoid adding new logic to legacy `thereisnohr/`. Keep service boundaries intact.

## System Specifics

### Ingestion Pipeline
- **Parsing:** Extracts PDF markdown, cleans artifacts, detects headings, and maps to canonical sections.
- **Identity Resolution:** Rules-first approach using deterministic signals (email, phone, name) with optional model fallback for low-confidence names.
- **Deduplication:** Uses both `resumes.source_file` and `resumes.content_hash`.
- **Embeddings:** Generated for non-skill sections and persisted with model metadata and content hashes.
- **Signals:** Structured candidate profile (`signals_json`) is extracted via LLM after parsing and stored on the `resumes` table.
- **Metaflow:** Ingests PDFs in parallel, commits per file, and emits run-level reports.

### Retrieval & Ranking
- **Funnel Logic:** Multi-stage retrieval: Vector Retrieval (Wide Net) -> Deterministic Score (Heuristic Filter) -> LLM Reranking (Fine Refinement).
- **Hybrid Scoring:** Combines semantic similarity scores with deterministic skill-overlap heuristics.
- **Explanations:** Top candidates receive qualitative AI-generated explanations (`RankExplanation`).
- **Matches:** All ranking outcomes and reasoning are persisted to the `matches` table.

### LLM Layer
- **Client:** Model access must go through `LLMClient` and alias routing.
- **Outputs:** Structured outputs are validated against Pydantic schemas; retries are bounded.
- **Embeddings:** Generated via `embed` or `embed_with_meta` with alias-based routing.

## Current Status & Limitations
- **Stage 4 Complete:** Retrieval and Hybrid Ranking are fully implemented and integrated into the CLI.
- **API:** The API surface is minimal (health endpoint only). Exposing ranking via API is pending.
- **Config:** Model alias config may contain model string typos (verify before use).
