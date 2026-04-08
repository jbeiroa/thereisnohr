# thereisnohr

`thereisnohr` is a small, flexible, provider-agnostic Applicant Tracking System (ATS).

It provides a complete end-to-end pipeline for resume processing, from PDF ingestion to AI-driven candidate matching and interview preparation.

## Core Capabilities

- **Multi-Source Ingestion**: Add resumes via local folder batch processing or direct PDF uploads through the web UI.
- **Intelligent Parsing**: Extract markdown from PDFs with automated section detection and bilingual support (English/Spanish).
- **Identity Resolution**: Deterministic and LLM-backed candidate identification to prevent duplicates.
- **Structured Signal Extraction**: Derivation of skills, experience, and education from resumes and job descriptions using LLMs.
- **Hybrid Retrieval & Ranking**: A multi-stage funnel combining vector search (`pgvector`), deterministic skill matching, and LLM reranking.
- **Evidence-Based Explanations**: Transparent match rationales grounded in resume quotes with explicit gap and risk analysis.
- **Automated Interview Preparation**: Generation of tailored technical and behavioral questions based on candidate-job fit.
- **Modern Local UI**: A multi-page Streamlit application for managing jobs, ingesting resumes, and reviewing matches.
- **Async API**: A FastAPI backend with a database-backed task queue for long-running LLM and processing tasks.

## Repository Map

- `src/api/`: FastAPI application and REST routers.
- `ui/`: Streamlit web application.
- `src/ingest/`: Ingestion service, PDF parser, and Metaflow orchestration.
- `src/extract/`: Structured signal extraction for candidates and jobs.
- `src/retrieval/`: Semantic vector retrieval using `pgvector`.
- `src/ranking/`: Hybrid scoring and LLM reranking logic.
- `src/storage/`: SQLAlchemy engine, models, and repositories.
- `src/llm/`: Provider-agnostic LLM abstraction (`LLMClient`) and LiteLLM integration.
- `src/core/`: Runtime settings and structured logging.
- `alembic/`: Database migrations.
- `config/`: Model aliases and provider configurations.
- `tests/`: Unit and integration test suite.
- `docs/`: Technical guides and architectural documentation.

## Quickstart (uv)

1. **Sync dependencies**:
   ```bash
   uv sync --all-extras
   ```

2. **Setup environment**:
   Copy `.env.example` to `.env` and adjust your `DATABASE_URL` and LLM provider keys (e.g., `OPENAI_API_KEY`).

3. **Initialize Database**:
   ```bash
   uv run alembic upgrade head
   ```

4. **Run the Application**:
   - Start the Backend: `uv run uvicorn src.api.app:app`
   - Start the Frontend: `uv run streamlit run ui/app.py`

## Configuration

Configuration is managed via `src/core/config.py` using `pydantic-settings`. Key settings include:
- `DATABASE_URL`: Postgres connection string.
- `*_MODEL_ALIAS`: Routing aliases for different LLM tasks (defined in `config/model_aliases.yaml`).
- `LLM_TIMEOUT_SECONDS` & `LLM_MAX_RETRIES`: Reliability controls.

## Design Philosophy

- **Provider Agnostic**: Switch between Ollama, OpenAI, Anthropic, etc., by changing simple configuration aliases.
- **Durable Foundations**: Postgres + pgvector provides a single source of truth for metadata and embeddings.
- **Async First**: Heavy computations and LLM calls are handled as background tasks with real-time status tracking.
- **Surgical Logic**: Modular architecture allows improving ranking heuristics or parsing rules without side effects.

## Additional Documentation

- `docs/architecture.md`: Detailed system design and tradeoffs.
- `docs/full-software-guide.md`: Canonical technical walkthrough for developers.
