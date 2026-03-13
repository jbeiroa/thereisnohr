# AGENTS

## Purpose and audience
This file orients coding agents and contributors working on `thereisnohr`. It summarizes the current architecture, workflows, and constraints so changes stay consistent with the codebase.

## Source of truth
When sources disagree, prefer, in order:
1. Current code under `src/` and runtime behavior
2. Tests under `tests/`
3. Documentation under `docs/`
4. Plans under `.plans/`

## Project snapshot (current capabilities)
- Runtime foundations: typed settings (`src/core/config.py`) and structured logging with run IDs (`src/core/logging.py`).
- Persistence layer: SQLAlchemy models and repositories, Alembic migrations, Postgres + pgvector.
- LLM layer: provider-agnostic client, alias registry, structured output parsing, and embedding generation.
- Ingestion pipeline: PDF parsing, identity resolution, dedupe by content hash, section extraction, Metaflow orchestration, and run reporting artifacts.
- Entrypoints: Typer CLI and FastAPI app shell with health endpoint.

## Architecture map and module responsibilities
- `src/core/`: settings and logging utilities.
- `src/storage/`: SQLAlchemy base/session, ORM models, repositories.
- `src/llm/`: provider-agnostic client, registry, errors, and factory.
- `src/ingest/`: parser, identity resolution, model fallback, ingestion service, Metaflow flow, telemetry.
- `src/extract/`: extraction service boundary and types (currently stubbed).
- `src/retrieval/`: retrieval boundary (currently stubbed).
- `src/ranking/`: ranking service boundary and types (currently stubbed).
- `src/api/`: FastAPI app with `/health` endpoint.
- `src/cli.py`: Typer CLI commands (`ingest`, `index`, `rank`, `ingest-flow-help`).
- `alembic/`: migration runtime and revisions.
- `config/`: model alias configuration (`config/model_aliases.yaml`).
- `scripts/`: backfill/repair utilities.
- `tests/`: unit and integration tests.
- `docs/`: architecture and usage guides.
- `thereisnohr/`: legacy pipeline (historical reference only; do not extend for new work).

## Key workflows and commands
### Setup
```bash
uv sync --all-extras --dev
cp .env.example .env
```

### Tests
```bash
uv run pytest -q
uv run pytest -q -m integration
```

### Migrations
```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head --sql
```

### CLI and API
```bash
uv run ats --help
uv run uvicorn src.api.app:app --reload
```

### Ingestion flow
```bash
uv run python src/ingest/pdf_ingestion_flow.py run --input-dir data --pattern '*.pdf'
```

## Ingestion pipeline specifics
- Parser extracts PDF markdown, cleans artifacts, detects headings, maps to canonical sections, and returns `sections`, `section_items`, and `links`.
- Identity resolution uses deterministic signals with a rules-first approach and optional model fallback for low-confidence names.
- Dedupe uses both `resumes.source_file` and `resumes.content_hash`.
- Section routing can call an LLM for recategorization when confidence is low or `general`.
- Embeddings are generated for non-skill sections and persisted with model metadata and content hashes.
- Metaflow flow ingests PDFs in parallel, commits per file, and emits run-level reports/metrics.

## LLM layer usage
- Model access must go through `LLMClient` and alias routing in `config/model_aliases.yaml`.
- Structured outputs are validated against Pydantic schemas; retries are bounded.
- Embeddings are generated via `embed` or `embed_with_meta` with alias-based routing.

## Current limitations
- Extraction, retrieval, and ranking services are mostly stubs.
- CLI `ingest`, `index`, and `rank` commands are placeholders.
- API surface is minimal (`/health` only).
- Model alias config contains probable model string typos (verify before production use).

## Contribution expectations
- Prefer modifying `src/` modules; avoid adding new logic to legacy `thereisnohr/`.
- Keep service boundaries intact (ingest/extract/retrieval/ranking).
- Add tests for any new behavior or bug fixes.
- Keep changes small and focused; avoid introducing speculative abstractions.
