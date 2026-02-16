# thereisnohr

`thereisnohr` is being rebuilt as a small, flexible, provider-agnostic Applicant Tracking System (ATS).

This branch implements **Stage 0** (foundation/scaffolding) and **Stage 1** (durable ATS schema).

## Why this reengineering exists

The original project goal was resume selection automation for a specific school context. The new direction broadens scope to a general ATS that can:

- ingest resumes and job descriptions,
- extract candidate signals,
- index candidates for semantic retrieval,
- rank top-k applicants,
- produce transparent explanations for hiring decisions.

The first two stages intentionally focus on reliability and architecture, not model quality yet:

- Stage 0 provides a clean runtime shape and testable boundaries.
- Stage 1 provides data durability and query foundations (Postgres + pgvector).

## Current capabilities (Stage 0/1)

Implemented now:

- flat `src/` code layout with explicit module boundaries,
- typed environment configuration (`pydantic-settings`),
- structured logging with per-run IDs,
- CLI skeleton (`ats ingest`, `ats index`, `ats rank`),
- FastAPI app skeleton (`/health`),
- SQLAlchemy models for ATS entities,
- Alembic migrations and pgvector extension setup,
- repository classes for initial DB access patterns,
- uv-based dependency and lockfile workflow,
- baseline tests for config, schema registration, and CLI wiring.

Not implemented yet (planned in Stage 2+):

- provider-agnostic LLM orchestration via LiteLLM,
- real resume parsing and section extraction pipeline,
- retrieval/ranking logic and score explanations,
- production API endpoints beyond healthcheck.

## Repository map

- `src/core/`: runtime settings and logging.
- `src/cli.py`: CLI entrypoint and commands.
- `src/api/`: FastAPI app.
- `src/ingest/`: ingestion service boundary.
- `src/extract/`: extraction service boundary.
- `src/retrieval/`: retrieval service boundary.
- `src/ranking/`: ranking service boundary.
- `src/storage/`: SQLAlchemy engine, models, repositories.
- `alembic/`: migration runtime and revision scripts.
- `tests/`: foundational test suite for Stage 0/1.
- `docs/`: architecture and usage documentation.

## Quickstart (uv)

1. Sync dependencies and create virtual environment:

```bash
uv sync --all-extras --dev
```

2. Run tests:

```bash
uv run pytest -q
```

3. Inspect CLI commands:

```bash
uv run ats --help
```

4. Run API locally:

```bash
uv run uvicorn src.api.app:app --reload
```

5. Run migrations:

```bash
uv run alembic upgrade head
```

## Configuration

Copy `.env.example` to `.env` and adjust values:

```env
APP_NAME=thereisnohr
ENVIRONMENT=dev
LOG_LEVEL=INFO
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/thereisnohr
EMBEDDING_MODEL_ALIAS=embedding_default
SUMMARIZER_MODEL_ALIAS=summarizer_default
```

Configuration is loaded by `src/core/config.py` with typed defaults and env overrides.

## Intended usage today

Current commands are scaffolding-oriented and useful for validating wiring, environment, and developer setup:

```bash
uv run ats ingest /path/to/resume.txt
uv run ats index
uv run ats rank 123 --top-k 5
```

These are placeholders by design; they define stable interfaces that Stage 2+ will implement.

## Design reasoning (short)

- **Flat `src/` layout**: keeps imports direct and avoids nested package overhead while the architecture is evolving quickly.
- **Postgres + pgvector**: one durable store for structured metadata + vectors, minimizing operational complexity.
- **Alembic from day one**: migration discipline early avoids schema drift later.
- **Service boundaries now, logic later**: isolates future ATS behaviors behind stable module contracts.
- **uv over Poetry**: faster lock/sync workflow and simpler toolchain.

## Additional docs

- `docs/architecture.md`: detailed architecture and design tradeoffs.
- `docs/stage-0-1-guide.md`: deep usage walkthrough and examples for current code.

## Legacy code note

The older implementation still exists under `thereisnohr/` (legacy pipeline modules) and is not yet migrated into the new `src/` architecture. Stages 2+ will progressively replace legacy paths with new service flows.
