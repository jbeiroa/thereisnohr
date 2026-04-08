# Architecture

This document explains the system design and architectural tradeoffs of `thereisnohr`.

## 1) Architectural Goals

The system is designed for:
- **Clear module boundaries**: Each functional area (ingest, extract, retrieval, ranking) is isolated behind a service contract.
- **Durable schema**: PostgreSQL + `pgvector` acts as the single source of truth for both structured metadata and semantic embeddings.
- **Provider Agnosticism**: The LLM layer is abstracted via `LLMClient` and LiteLLM, allowing models to be swapped via configuration.
- **Asynchronous Execution**: Long-running tasks (parsing, LLM calls) are processed in the background to maintain a responsive UI.
- **Low-friction local development**: Uses `uv` for dependency management and Streamlit for a simple, effective frontend.

## 2) High-Level Component View

Functional flow:
1. **Ingest**: PDF resumes are received via the API (upload) or local folder discovery.
2. **Process (Async)**: Background tasks handle markdown extraction, identity resolution, and structured signal extraction.
3. **Persist**: All artifacts, including parsed sections and extracted skills, are stored in PostgreSQL.
4. **Retrieve**: When a job is ranked, `pgvector` performs a semantic search against the database.
5. **Rank**: A hybrid algorithm combines vector scores with deterministic skill overlap and LLM-based qualitative reranking.
6. **Interface**: Users interact with the system through a multi-page Streamlit UI connected to a FastAPI backend.

## 3) Module breakdown

### `src/api/`
- **FastAPI Core**: Defines the REST API surface.
- **Async Task Runner**: Implements a zero-dependency task queue using `BackgroundTasks` and database state tracking (`AsyncTask` model).
- **Routers**: Modular endpoints for Jobs, Candidates, Matches, and Ingestion.

### `ui/`
- **Streamlit App**: A multi-page frontend providing an intuitive dashboard for recruiters.
- **API Client**: Encapsulates all backend communication and task polling logic.

### `src/ingest/`
- **Parser**: Hardened PDF-to-markdown engine using `pymupdf4llm` with custom cleaning rules.
- **Identity Resolution**: Multi-stage resolution (deterministic rules -> LLM fallback) to uniquely identify candidates.
- **Metaflow**: Orchestrates batch ingestion pipelines for high-throughput processing.

### `src/extract/`
- **Signal Extraction**: Turns messy resume and job description text into structured JSON schemas (skills, experience, etc.) using LLMs.

### `src/retrieval/`
- **Semantic Search**: Uses cosine similarity via `pgvector` to find candidates based on the semantic context of their resumes.

### `src/ranking/`
- **Hybrid Scoring**: Weights vector retrieval against hard-skill overlap.
- **LLM Reranker**: Provides the "final mile" of intelligence, offering qualitative fits and risk analysis.

### `src/storage/`
- **Durable Models**: SQLAlchemy 2.0 models for all ATS entities.
- **Repository Pattern**: Centralizes database access logic to ensure consistency and testability.

### `src/llm/`
- **Abstraction Layer**: `LLMClient` provides a unified interface for structured generation and embeddings.
- **Alias Registry**: Maps logical task names (e.g., `ranker_default`) to specific model/provider configurations.

## 4) Data Model Highlights

- **`candidates`**: Global person-level identity.
- **`resumes`**: Multiple versions of resumes linked to one candidate, storing raw text and extracted `signals_json`.
- **`matches`**: Historical records of ranking events, including AI-generated `reasons_json` and `interview_pack_json`.
- **`async_tasks`**: Real-time status and result tracking for background operations.

## 5) Design Decisions

- **Postgres + pgvector**: Chosen to keep infrastructure simple. One database handles relational data, JSON metadata, and vector embeddings.
- **Flat `src/` Layout**: Keeps imports direct and reduces cognitive overhead during development.
- **Alembic**: Mandatory migration discipline ensures the schema remains stable and reproducible.
- **Background Tasks**: Essential for LLM workflows where latency can be high (10s-60s).
