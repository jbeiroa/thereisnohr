# thereisnohr

`thereisnohr` is being rebuilt as a small, flexible, provider-agnostic Applicant Tracking System (ATS).

This branch implements **Stage 0** (foundation/scaffolding), **Stage 1** (durable ATS schema), **Stage 2** (provider-agnostic LLM layer), **Stage 3** (ingestion/parsing slice), and **Stage 4** (retrieval and hybrid ranking).

## Why this reengineering exists

The original project goal was resume selection automation for a specific school context. The new direction broadens scope to a general ATS that can:

- ingest resumes and job descriptions,
- extract candidate signals,
- index candidates for semantic retrieval,
- rank top-k applicants,
- produce transparent explanations for hiring decisions.

The first stages focused on reliability and architecture, while Stage 4 introduces the core matching intelligence:

- Stage 0 provides a clean runtime shape and testable boundaries.
- Stage 1 provides data durability and query foundations (Postgres + pgvector).
- Stage 4 provides the multi-stage ranking funnel (Vector + Deterministic + LLM).

## Current capabilities (Stage 0/1/2/3/4 slice)

Implemented now:

- flat `src/` code layout with explicit module boundaries,
- typed environment configuration (`pydantic-settings`),
- structured logging with per-run IDs,
- CLI tools for ingestion and ranking (`ats ingest-job`, `ats rank`),
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
- optional model-based fallback for low-confidence name extraction (rules-first, threshold-gated).
- run-level ingestion metrics/reporting artifacts in Metaflow (`run_report` + `run_metrics` card).
- OCR-aware markdown extraction path via `pymupdf-layout` (active when system `tesseract` is available).
- Stage 3/4 experimentation notebook suite under `notebooks/` (parser QA, ingestion service checks, repository smoke checks, LLM registry checks, and extraction testing).
- **Hybrid Retrieval & Ranking Pipeline:** Multi-stage funnel (Vector Retrieval -> Deterministic Scoring -> LLM Reranking).
- **Job Posting Ingestion:** Structured requirement extraction from job descriptions.
- **Candidate Signal Extraction:** Automatic derivation of skills and experience from parsed resumes.

Not implemented yet (planned in Stage 5+):

- production API endpoints beyond healthcheck,
- web UI for recruiters.

## Repository map

- `src/core/`: runtime settings and logging.
- `src/cli.py`: CLI entrypoint and commands.
- `src/api/`: FastAPI app.
- `src/ingest/`: ingestion service boundary and Metaflow flow.
- `src/extract/`: structured signal extraction (candidates and jobs).
- `src/retrieval/`: semantic vector retrieval.
- `src/ranking/`: hybrid scoring and LLM reranking logic.
- `src/storage/`: SQLAlchemy engine, models, repositories.
- `src/llm/`: provider-agnostic client interface, alias registry, LiteLLM provider.
- `alembic/`: migration runtime and revision scripts.
- `config/model_aliases.yaml`: model routing aliases and default provider params.
- `tests/`: foundational test suite and stage-specific integration tests.
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

6. Run ingestion flow:

```bash
uv run python src/ingest/pdf_ingestion_flow.py run --input-dir data --pattern '*.pdf'
```

7. Ingest a job and rank candidates:

```bash
uv run ats ingest-job data/job_descriptions.txt --title "Software Engineer"
uv run ats rank 1 --top-k 5
```

## Configuration

Copy `.env.example` to `.env` and adjust values:

```env
APP_NAME=thereisnohr
ENVIRONMENT=dev
LOG_LEVEL=INFO
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/thereisnohr
EMBEDDING_MODEL_ALIAS=embedding_default
SUMMARIZER_MODEL_ALIAS=summarizer_default
EXTRACTOR_MODEL_ALIAS=extractor_default
RANKER_MODEL_ALIAS=ranker_default
```

Configuration is loaded by `src/core/config.py` with typed defaults and env overrides.

## Intended usage today

The CLI provides a full end-to-end flow from resume ingestion to candidate ranking:

```bash
# 1. Ingest resumes (Batch)
uv run python src/ingest/pdf_ingestion_flow.py run --input-dir data

# 2. Ingest a job description
uv run ats ingest-job data/job_descriptions.txt --title "Python Expert"

# 3. Rank candidates for the job (ID 1)
uv run ats rank 1 --top-k 3
```


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
