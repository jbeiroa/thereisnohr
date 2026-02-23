# thereisnohr

`thereisnohr` is being rebuilt as a small, flexible, provider-agnostic Applicant Tracking System (ATS).

This branch implements **Stage 0** (foundation/scaffolding), **Stage 1** (durable ATS schema), starts **Stage 2** (provider-agnostic LLM layer), and delivers a substantial **Stage 3** ingestion/parsing slice.

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

## Current capabilities (Stage 0/1/2/3 slice)

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
- provider-agnostic LLM abstraction (`LLMClient`) with a LiteLLM-backed implementation,
- model alias registry loaded from `config/model_aliases.yaml`,
- schema-validated structured generation with retry handling,
- alias-based embedding generation through LiteLLM.
- Metaflow orchestration flow for PDF resume ingestion into Postgres.
- parser and ingestion services that reuse legacy extraction/cleaning ideas in the new architecture.
- parser precleaning + heading span detection + canonical section mapping.
- mandatory section behavior for noisy conversions: absorb consecutive `general` spans into single-line non-`general` sections.
- parser output contract with `sections`, `section_items`, and extracted `links`.
- deterministic content-based candidate identity resolution (`name`/`email`/`phone` + identity confidence diagnostics).
- resume content-hash idempotency checks in ingestion.
- Stage 3 experimentation notebook suite under `notebooks/` (parser QA, ingestion service checks, repository smoke checks, and LLM registry checks).

Not implemented yet (planned in Stage 3/4+):

- optional model-based fallback for low-confidence name extraction,
- run-level ingestion metrics/reporting artifacts in Metaflow,
- optional OCR fallback for scanned PDFs (explicitly not prioritized right now),
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
- `src/llm/`: provider-agnostic client interface, alias registry, LiteLLM provider.
- `src/ingest/`: parser, ingestion service, and Metaflow PDF ingestion flow.
- `alembic/`: migration runtime and revision scripts.
- `config/model_aliases.yaml`: model routing aliases and default provider params.
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

Integration tests (ephemeral Postgres, opt-in):

```bash
uv run pytest -q -m integration
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

6. Run Stage 3 ingestion flow:

```bash
uv run python src/ingest/pdf_ingestion_flow.py run --input-dir data --pattern '*.pdf'
```

## Configuration

Copy `.env.example` to `.env` and adjust values:

```env
APP_NAME=thereisnohr
ENVIRONMENT=dev
LOG_LEVEL=INFO
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/thereisnohr_stage1
EMBEDDING_MODEL_ALIAS=embedding_default
SUMMARIZER_MODEL_ALIAS=summarizer_default
INGEST_FLOW_METRICS_ENABLED=true
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

## Stage 2 usage (LLM abstraction)

Example: build the default client and run structured generation:

```python
from pydantic import BaseModel

from src.llm.factory import build_default_llm_client


class CandidateSummary(BaseModel):
    name: str
    skills: list[str]


client = build_default_llm_client()
result = client.generate_structured(
    prompt="Summarize candidate in JSON with fields: name, skills",
    schema=CandidateSummary,
    model_alias="summarizer_default",
)
print(result.model_dump())
```

Example: embeddings through alias routing:

```python
client = build_default_llm_client()
vectors = client.embed(
    texts=["Physics teacher with 5 years experience", "Python and SQL instructor"],
    embedding_model_alias="embedding_default",
)
print(len(vectors))
```

## Design reasoning (short)

- **Flat `src/` layout**: keeps imports direct and avoids nested package overhead while the architecture is evolving quickly.
- **Postgres + pgvector**: one durable store for structured metadata + vectors, minimizing operational complexity.
- **Alembic from day one**: migration discipline early avoids schema drift later.
- **Service boundaries now, logic later**: isolates future ATS behaviors behind stable module contracts.
- **uv over Poetry**: faster lock/sync workflow and simpler toolchain.

## Additional docs

- `docs/architecture.md`: detailed architecture and design tradeoffs.
- `docs/stage-0-1-guide.md`: deep usage walkthrough and examples for current code.
- `docs/stage-2-llm.md`: Stage 2 LiteLLM layer, alias routing, and structured output usage.
- `docs/stage-3-ingestion.md`: legacy-reuse analysis and Metaflow PDF ingestion pipeline details.

## Notebook suite

Non-legacy experimentation notebooks are in `notebooks/`:

- `parsers_testing.ipynb`: canonical parser QA notebook.
- `ingestion_service_testing.ipynb`: ingestion service checks without Metaflow execution.
- `repositories_smoke_testing.ipynb`: repository contract smoke checks against local DB.
- `llm_registry_testing.ipynb`: alias registry checks + optional credential-gated live calls.

See `notebooks/README.md` for execution order, prerequisites, pass criteria, and troubleshooting.

## Legacy code note

The older implementation still exists under `thereisnohr/` (legacy pipeline modules) and is not yet migrated into the new `src/` architecture. Stages 2+ will progressively replace legacy paths with new service flows.
