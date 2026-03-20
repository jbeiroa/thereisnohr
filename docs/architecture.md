# Architecture (Stage 0-4 implemented)

This document explains what was introduced in the reengineering baseline and why.

## 1) Architectural goals for early stages

Stage 0 through Stage 4 optimize for:

- clear module boundaries,
- deterministic environment setup,
- durable schema + migration discipline,
- multi-stage candidate matching intelligence,
- low-friction local development.

The implementation has matured from structural foundations to a functional ATS core.

## 2) High-level component view

Functional flow:

1. **Ingest:** PDF resume artifacts (Metaflow).
2. **Extract:** Candidate signals and job requirements (LLM).
3. **Persist:** Structured data, signals, and embeddings (Postgres + pgvector).
4. **Retrieve:** Vector search for semantic candidates.
5. **Rank:** Hybrid scoring (Deterministic + LLM Reranking).
6. **Explain:** AI-generated reasoning for match scores.

What exists now:

- complete implementation for steps 1-5,
- durable DB schema for storage and matching history,
- operational primitives (config/logging/CLI/API/tests).

## 3) Module-by-module breakdown

## `src/core/`

- `config.py`: central typed settings via `pydantic-settings`.
- `logging.py`: structured logging helper + generated `run_id` to correlate events.

## `src/cli.py`

CLI commands:

- `ingest-job`: Ingest and extract requirements from a JD.
- `rank`: Retrieve and rank candidates for a job.
- `ingest-flow-help`: Helper for batch resume ingestion.

## `src/api/app.py`

- FastAPI app with `/health` endpoint.

## `src/ingest/`

Substantive ingestion behavior:

- PDF markdown extraction (`pymupdf4llm`),
- heading span detection and canonical mapping,
- deterministic identity resolution (Rules + LLM Fallback),
- Metaflow flow for batch orchestration.

## `src/extract/`

Structured signal extraction:

- `CandidateSignals`: Skills, experience, education extraction from resumes.
- `JobRequirements`: Hard/soft skills, years of experience, and education extraction from JDs.

Reasoning:
- uses LLM structured generation to turn messy text into searchable, scorable schema.

## `src/retrieval/`

Semantic retrieval layer:

- `RetrievalService`: Performs vector search against `resume_sections` using `pgvector`.
- Returns a "wide net" of candidates with semantic similarity scores.

## `src/ranking/`

Hybrid ranking and refinement:

- `Deterministic Scoring`: 50/50 weighted average of vector similarity and hard-skill overlap.
- `LLM Reranking`: Uses a ranker model to provide qualitative assessments and explanations for top candidates.

Reasoning:
- balances the "intuition" of embeddings with the "precision" of keyword/signal matching.

## `src/storage/`

- `db.py`: SQLAlchemy base, engine/session creation.
- `models.py`: ATS entities and relationships (including `signals_json` and `matches`).
- `repositories.py`: repository layer for transactional access.

## `alembic/`

- migration runtime and schema revisions (Initial -> Identity -> Embeddings -> Ranking).

## 4) Data model introduced in Stage 1-4

Tables:

- `candidates`: person-level identity/contact metadata.
- `resumes`: raw source text, parsed structure, and **`signals_json`**.
- `resume_sections`: normalized sections (experience, skills, education, etc.).
- `job_postings`: job definitions and **`requirements_json`**.
- `embeddings`: vectors tied to resume sections.
- **`matches`**: score records linking job and candidate plus **`reasons_json`**.

## 5) Why Postgres + pgvector

Chosen to balance flexibility and operational simplicity.

Benefits:

- one durable datastore for transactional + vector workloads,
- native filtering and joins for hybrid scoring,
- good migration story with Alembic.

## 6) Why flat `src/` layout

Current code is at `src/<module>` rather than `src/<package>/<module>`.

Benefits:
- simpler import graph, faster refactoring, and reduced indirection.

## 7) Why uv

`uv` replaced Poetry for faster lock/sync operations and modern dependency management.

## 8) Extensibility path toward Stage 5+

The current structure supports:

- **Stage 5**: Richer explanations and interview prep generation.
- **Stage 6**: Production API expansion and web-based recruiter dashboard.
- **Continuous Improvement**: Tuning ranking heuristics and model prompts.

## 9) Notebook-driven experimentation

The repository includes a notebook suite to validate components:

- `notebooks/parsers_testing.ipynb`: parser QA.
- `notebooks/extraction_service_testing.ipynb`: LLM signal extraction QA.
- `notebooks/ingestion_service_testing.ipynb`: service helper checks.
- `notebooks/repositories_smoke_testing.ipynb`: repository contract smoke checks.
- `notebooks/llm_registry_testing.ipynb`: alias registry checks.

