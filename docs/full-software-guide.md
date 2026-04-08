# Full Software Guide

## Purpose and Reader
This guide is the canonical technical walkthrough of the `thereisnohr` codebase for engineers who need to understand, operate, and extend the system. It describes the complete implementation as of the final stage.

## System Snapshot
`thereisnohr` is a complete Applicant Tracking System (ATS) featuring:
- **Async API**: FastAPI-based REST backend with database-backed background task management.
- **Modern UI**: Multi-page Streamlit application for recruiters.
- **Advanced Ingestion**: Multi-stage PDF parsing, identity resolution, and structured extraction.
- **Hybrid Ranking**: Vector retrieval (`pgvector`) combined with deterministic heuristics and LLM reranking.
- **Full Persitence**: Robust SQLAlchemy models and Alembic migrations.

## Repository Map
- `src/api/`: REST API surface and async task framework.
- `ui/`: Streamlit frontend application.
- `src/ingest/`: PDF parsing, candidate identity resolution, and Metaflow flows.
- `src/extract/`: Signal extraction logic for resumes and job descriptions.
- `src/retrieval/`: Semantic vector retrieval service.
- `src/ranking/`: Hybrid scoring and LLM reranking services.
- `src/storage/`: Database models, repositories, and migration runtime.
- `src/llm/`: Provider-agnostic client and model alias registry.
- `src/core/`: Runtime configuration and structured logging.
- `config/`: Model routing aliases and fallback policies.
- `tests/`: Unit and integration test suites.

---

## Architecture Layers

### 1) Runtime & Configuration
- **Settings**: Defined in `src/core/config.py` using `pydantic-settings`. Loads from `.env`.
- **Logging**: Structured JSON logging with `run_id` correlation for all internal and external (LLM) calls.

### 2) Persistence Layer
- **Database**: PostgreSQL with `pgvector` for semantic search.
- **Models**: SQLAlchemy 2.0 `Mapped` styles in `src/storage/models.py`.
- **Repositories**: Standardized CRUD and complex query logic in `src/storage/repositories.py`.
- **Migrations**: Alembic-managed schema revisions.

### 3) LLM Abstraction
- **LLMClient**: Abstract contract for structured generation and embeddings.
- **LiteLLM**: Concrete implementation supporting hundreds of providers (OpenAI, Ollama, Anthropic, etc.).
- **Alias Registry**: Decouples feature logic from specific models. Features request an alias (e.g., `ranker_default`), and the registry routes it to the configured provider.

### 4) Ingestion & Parsing
- **Parser**: Uses `pymupdf4llm` to convert PDFs to markdown, followed by custom cleaning and heading detection.
- **Identity Resolution**: Determines if a resume belongs to an existing candidate using deterministic signals (email, phone) and LLM fallback for names.
- **Ingestion Service**: Orchestrates the per-file pipeline (parse -> identify -> extract signals -> persist).
- **Metaflow**: Used for high-volume batch ingestion from local directories.

### 5) Retrieval & Ranking
- **Stage 1: Vector Retrieval**: Wide-net search using cosine similarity on resume section embeddings.
- **Stage 2: Deterministic Scorer**: Heuristic filter based on explicit hard-skill overlap between the JD and candidate signals.
- **Stage 3: LLM Reranking**: Qualitative refinement of top candidates, generating fit summaries and gap/risk analysis.

### 6) API & UI (Interface Layer)
- **FastAPI**: Provides endpoints for job management, resume uploads, and ranking triggers.
- **AsyncTask Runner**: A zero-dependency worker that executes long-running functions using FastAPI's `BackgroundTasks` while updating the `async_tasks` table for UI polling.
- **Streamlit**: A dashboard for recruiters to upload files, manage job postings, and review/export candidate rankings.

---

## Developer Runbook

### Setup
```bash
uv sync --all-extras
cp .env.example .env
# Edit .env with your database and API keys
```

### Database Operations
```bash
uv run alembic upgrade head
```

### Running the App
1. **Start Backend**: `uv run uvicorn src.api.app:app`
2. **Start Frontend**: `uv run streamlit run ui/app.py`

### Testing
```bash
uv run pytest -q
# For database integration tests (requires Docker)
uv run pytest -q -m integration
```

---

## Technical Contracts

### Public REST API
- `POST /api/ingest/upload`: Upload PDF resumes.
- `POST /api/jobs`: Create a job and extract requirements.
- `POST /api/jobs/{id}/rank`: Start the ranking process.
- `GET /api/tasks/{id}`: Poll for background task status.
- `GET /api/matches`: List ranked candidates for a job.

### Model Alias System
Aliases are defined in `config/model_aliases.yaml`:
- `embedding_default`: Used for semantic indexing.
- `extractor_default`: Used for structured signal extraction.
- `ranker_default`: Used for qualitative reranking and explanations.
- `explainer_default`: Used for interview prep pack generation.
