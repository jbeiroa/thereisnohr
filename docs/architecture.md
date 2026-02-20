# Architecture (Stage 0/1 baseline + Stage 2/3 in progress)

This document explains what was introduced in the reengineering baseline and why.

## 1) Architectural goals for early stages

Stage 0 and Stage 1 optimize for:

- clear module boundaries,
- deterministic environment setup,
- durable schema + migration discipline,
- easy extension into ATS-specific behaviors,
- low-friction local development.

The implementation is intentionally minimal in business behavior and strong in structure.

## 2) High-level component view

Flow target (final product direction):

1. Ingest resume/job artifacts.
2. Normalize and extract structured candidate signals.
3. Persist structured data and embeddings.
4. Retrieve/rank candidate top-k per job.
5. Generate explainable outputs.

What exists now:

- service boundaries for steps 1-4,
- durable DB schema for step 3,
- partial concrete implementation for step 1/2 in Stage 3 parser + ingestion flow,
- operational primitives (config/logging/CLI/API/tests).

## 3) Module-by-module breakdown

## `src/core/`

- `config.py`: central typed settings via `pydantic-settings`.
- `logging.py`: structured logging helper + generated `run_id` to correlate events.

Reasoning:

- centralized settings avoid hard-coded paths and implicit assumptions,
- run-scoped logs enable future tracing across ingestion/extraction/ranking operations.

## `src/cli.py`

CLI commands:

- `ingest`
- `index`
- `rank`

Reasoning:

- defines stable operational contracts now,
- keeps future implementation backwards-compatible as internal logic matures.

## `src/api/app.py`

- FastAPI app with `/health` endpoint.

Reasoning:

- establishes service runtime shell early,
- enables future endpoint growth without changing base app wiring.

## `src/ingest/`, `src/extract/`, `src/retrieval/`, `src/ranking/`

`src/ingest/` now contains substantive Stage 3 behavior:

- PDF markdown extraction (`pymupdf4llm`),
- precleaning of conversion artifacts,
- heading span detection and canonical mapping,
- deterministic absorption rule for noisy headings,
- parsing output used by persistence (`sections`) and richer experimentation (`section_items`, `links`),
- Metaflow flow for batch orchestration.

`src/extract/`, `src/retrieval/`, and `src/ranking/` remain boundary-first with minimal placeholder behavior.

Reasoning:

- explicit boundaries now prevent monolithic pipeline code later,
- enables isolated testing and swapping implementation strategies (rules, LLM, hybrid).

## `src/storage/`

- `db.py`: SQLAlchemy base, engine/session creation.
- `models.py`: ATS entities and relationships.
- `repositories.py`: first repository interfaces for CRUD access.

Reasoning:

- data model-first approach anchors the system around persistent artifacts,
- repository layer keeps business logic decoupled from raw ORM queries.

## `alembic/`

- migration runtime and initial schema revision.

Reasoning:

- schema evolution should be explicit from first iteration,
- avoids ad-hoc DB setup and local/prod drift.

## 4) Data model introduced in Stage 1

Tables:

- `candidates`: person-level identity/contact metadata.
- `resumes`: raw source text and parsed structure per candidate document.
- `resume_sections`: normalized sections (experience, skills, education, etc.).
- `job_postings`: job definitions and requirements.
- `embeddings`: vectors tied to entities (`owner_type`, `owner_id`) with model/hash metadata.
- `matches`: score records linking job and candidate plus reasons payload.

Why this shape:

- separates immutable source (`resumes.raw_text`) from derived structure (`parsed_json`, `resume_sections`),
- supports multiple embedding granularities (resume-level and section-level),
- stores match artifacts explicitly for auditability and reproducibility.

## 5) Why Postgres + pgvector

Chosen to balance flexibility and operational simplicity.

Benefits:

- one durable datastore for transactional + vector workloads,
- native filtering and joins for hybrid scoring,
- good migration story with Alembic,
- local-first development and easy hosted upgrade path.

## 6) Why flat `src/` layout

Current code is at `src/<module>` rather than `src/<package>/<module>`.

Benefits in this project phase:

- simpler import graph while architecture is still moving,
- faster refactoring and file discovery,
- reduced indirection for a small team and early-stage codebase.

Tradeoff:

- less namespacing isolation than a nested package; acceptable at current scope.

## 7) Why uv

`uv` replaced Poetry for:

- faster lock/sync operations,
- straightforward virtualenv workflow,
- modern dependency group support,
- reduced packaging overhead for this iteration speed.

## 8) Extensibility path toward Stage 2+

The current structure is ready for:

- LiteLLM adapter layer in `src/llm/`,
- robust parsing and section extraction in `src/extract/`,
- embedding generation and vector indexing in `src/retrieval/`,
- hybrid ranking and explanation logic in `src/ranking/`,
- API expansion for ingestion/jobs/matches in `src/api/`.

## 9) Notebook-driven experimentation

The repository now has a non-legacy notebook suite to validate components in isolation without full pipeline execution:

- `notebooks/parsers_testing.ipynb`: parser QA and behavior assertions.
- `notebooks/ingestion_service_testing.ipynb`: service helper checks without Metaflow.
- `notebooks/repositories_smoke_testing.ipynb`: repository contract smoke checks against local DB.
- `notebooks/llm_registry_testing.ipynb`: alias registry checks and optional credential-gated live calls.
- `notebooks/README.md`: execution order, prerequisites, pass criteria, troubleshooting.

Design intent:

- accelerate iteration with assertion-driven experiments,
- reduce ad-hoc local scripts,
- keep learning/exploration isolated from production service code.

## 10) Testing strategy baseline

Current tests verify:

- settings load reliably,
- stage-1 tables are registered,
- CLI command wiring is functional,
- Stage 3 parser and ingestion helper behavior.

Next test increments:

- migration apply/rollback integration tests,
- repository CRUD tests against ephemeral Postgres,
- more fixture-driven ingest/extract quality tests with challenging PDFs,
- deterministic ranking contract tests.
