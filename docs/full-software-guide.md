# Full Software Guide

## Purpose and Reader
This guide is the canonical technical walkthrough of the `thereisnohr` codebase for engineers who need to understand, operate, and extend the system safely.

It consolidates:
- Current implementation truth from `src/`, `alembic/`, `config/`, `scripts/`, and `tests/`
- Existing docs under `docs/`
- The baseline reengineering plan under `.plans/REENGINEERING_PLAN.md`

When sources disagree, this guide prioritizes current code and tests.

## System Snapshot (Current Reality)
`thereisnohr` is an ATS reengineering project with:
- Strong foundations implemented: config, logging, DB schema, migrations, repositories, test harness, CLI/API shells
- A substantial Stage 3 ingestion vertical slice implemented: PDF parse -> identity resolution -> persistence -> Metaflow orchestration + telemetry
- A Stage 2 LLM abstraction implemented (LiteLLM, alias routing, fallback, normalized errors), partially integrated into ingestion fallbacks
- Extraction/retrieval/ranking service boundaries present but mostly scaffolding

## Repository Map
- `src/core/`: typed settings + logging utilities
- `src/storage/`: SQLAlchemy base/session, ORM models, repositories
- `src/llm/`: provider-agnostic client abstraction and LiteLLM implementation
- `src/ingest/`: parser, identity extraction, fallback resolver, ingestion service, Metaflow flow, telemetry
- `src/extract/`: extraction contracts + service stubs
- `src/retrieval/`: retrieval boundary + placeholder service
- `src/ranking/`: ranking contracts + placeholder service
- `src/api/`: FastAPI app (`/health`)
- `src/cli.py`: Typer CLI entrypoint
- `alembic/`: migration runtime + revisions
- `config/model_aliases.yaml`: model alias routes and fallback policies
- `scripts/`: backfill/repair utilities
- `tests/`: unit + integration tests
- `docs/`: architecture and stage guides
- `.plans/`: baseline plan (`REENGINEERING_PLAN.md`)
- `thereisnohr/`: legacy historical pipeline (not current architecture)

## Architecture Layers (Bottom to Top)

### 1) Runtime Foundations
Status: `Implemented`

#### Configuration
File: `src/core/config.py`

What it does:
- Defines `Settings` via `pydantic-settings`
- Loads `.env` and process env vars
- Caches settings via `get_settings()`

Important settings:
- App/env/log: `app_name`, `environment`, `log_level`
- Paths: `data_dir`, `model_aliases_path`
- DB: `database_url`
- LLM aliases: `embedding_model_alias`, `summarizer_model_alias`, `extractor_model_alias`, `explainer_model_alias`
- LLM runtime: `llm_timeout_seconds`, `llm_max_retries`
- Ingestion fallback controls and thresholds

#### Logging
File: `src/core/logging.py`

What it does:
- Configures structured logging format with `run_id`
- Provides `RunLoggerAdapter` and `get_run_logger(name)`

Operational intent:
- Correlate logs per logical run without external tracing infra.

### 2) Persistence Layer
Status: `Implemented`

#### SQLAlchemy Runtime
File: `src/storage/db.py`

What it does:
- Defines `Base` (`declarative_base`)
- Builds engine from settings
- Exposes `SessionLocal` and `get_session()`

#### Data Model
File: `src/storage/models.py`

Tables:
- `candidates`: identity/contact and links
- `resumes`: source, content hash, raw text, parsed artifacts, language
- `resume_sections`: normalized sections + metadata/tokens
- `job_postings`: job definition and optional requirements JSON
- `embeddings`: vector rows (pgvector), owner linkage, model/hash metadata
- `matches`: retrieval/rerank/final scores and reasons

#### Repositories
File: `src/storage/repositories.py`

What exists:
- `CandidateRepository`: create/get/upsert-by-identity with merge logic
- `ResumeRepository`: lookup by source file/content hash + create
- `ResumeSectionRepository`: create sections
- `JobPostingRepository`: create jobs

Notable behavior:
- Candidate upsert merges missing fields and unions links.
- Name replacement is quality-gated (`estimate_name_quality` + confidence thresholds).

### 3) Migration Layer
Status: `Implemented`

Files:
- `alembic/versions/20260216_0001_initial_schema.py`
- `alembic/versions/20260223_0002_identity_content_hash.py`

What exists:
- Initial schema + `vector` extension creation
- Added `resumes.content_hash` + index
- Added filtered unique index for non-null `candidates.external_id`
- Duplicate guard before creating uniqueness index

### 4) LLM Layer (Stage 2 Core)
Status: `Implemented (Partially Integrated)`

#### Contracts and Routing Types
File: `src/llm/types.py`

What exists:
- `ModelRoute`, `FallbackPolicy`, `ModelAlias`
- Metadata types: `LLMUsage`, `LLMAttempt`, `LLMCallMetadata`

Behavior:
- Alias definitions compile into LiteLLM Router model lists with ordered fallbacks.

#### Error Taxonomy
File: `src/llm/errors.py`

What exists:
- App-level errors (`LLMTimeoutError`, `LLMRateLimitError`, `LLMProviderError`, etc.)
- `coerce_provider_exception()` maps LiteLLM exceptions to stable app errors
- `error_type_for_exception()` for normalized telemetry labels

#### Registry
File: `src/llm/registry.py`

What it does:
- Loads and validates alias YAML config into typed `ModelAlias` objects
- Fails fast for missing/invalid config

#### Client
File: `src/llm/client.py`

Interfaces:
- `LLMClient` abstract contract (sync + async, with/without metadata)

Implementation:
- `LiteLLMClient` builds per-alias routers lazily
- Structured generation flow:
  - Router completion call
  - JSON extraction/parsing
  - Pydantic schema validation
  - normalized metadata
- Embedding flow:
  - Router embedding call
  - vector extraction + float coercion
  - metadata

#### Factory
File: `src/llm/factory.py`

What it does:
- Builds default `LiteLLMClient` from runtime settings and alias registry.

#### Alias Config
File: `config/model_aliases.yaml`

Current intent:
- Logical aliases for summarization, extraction, explanation, embeddings
- Ollama-first with OpenAI fallback chains

Current caveat in config values:
- Keep aliases in sync with provider availability and local model installs.

### 5) Ingestion Layer (Stage 3 Core)
Status: `Implemented (Primary Functional Slice)`

#### Entities
File: `src/ingest/entities.py`

Core contracts:
- `ParsedResume`
- `SectionItem`
- `IdentityCandidate`
- section diagnostics typed dicts

#### Parser
File: `src/ingest/parser.py`

What it does:
- PDF -> markdown (`pymupdf` + `pymupdf4llm`)
- markdown precleaning and block cleanup
- link extraction
- heading span detection
- heading canonical mapping (EN/ES and variants)
- absorption of noisy consecutive `general` spans into single-line non-general section context
- section outputs:
  - `sections: dict[str, str]`
  - `section_items: list[SectionItem]`
- lightweight language detection

#### Identity Resolution
File: `src/ingest/identity.py`

What it does:
- Extracts emails and phones (normalization + dedupe)
- Resolves name via rules-first heuristic scoring
- Optional model fallback path for low-confidence names
- Computes deterministic identity key:
  - email-first, then phone, then name, then content fallback
- Computes identity confidence and diagnostic signals

#### Model Fallback Resolver
File: `src/ingest/model_fallback.py`

What it does:
- Uses `LLMClient.generate_structured` for:
  - name fallback extraction
  - section fallback classification
- Restricts section labels to allowed canonical set
- Normalizes provider exceptions

#### Ingestion Service
File: `src/ingest/service.py`

Flow for one PDF:
1. Parse PDF -> `ParsedResume`
2. Compute content hash
3. Skip by existing source file or existing content hash
4. Resolve identity (rules + optional model fallback)
5. Upsert candidate by identity key
6. Build section payloads (optional LLM section rerouting for weak/general sections)
7. Persist resume + sections
8. Return `IngestionResult` with status and confidence metrics

Persisted artifacts:
- `resumes.parsed_json` includes:
  - `clean_text`, `links`, `parser_version`, `section_names`
  - `identity` payload (key, fields, confidence, signals)
- `resume_sections.metadata_json` includes parser + confidence + routing diagnostics

#### Metaflow Telemetry
File: `src/ingest/metaflow_telemetry.py`

What it does:
- Decorates steps via flow mutator
- Captures per-step timing/status/error events
- Builds summary reports:
  - status counts
  - reason breakdown
  - timing percentiles
  - quality summaries
- Supports run report card rendering helpers

#### Batch Flow
File: `src/ingest/pdf_ingestion_flow.py`

Step graph:
- `start`
- `discover_files`
- `ingest_one` (foreach)
- `join_results`
- `end`

Execution semantics:
- Per-file ingestion runs with isolated DB session and rollback on error
- Successful file ingests commit independently
- End step compiles and prints run summary, plus report/card artifact

### 6) Entrypoints
Status: `Partially Implemented`

#### CLI
File: `src/cli.py`

Commands:
- `ingest`
- `index`
- `rank`
- `ingest-flow-help`

Reality:
- `ingest/index/rank` are interface placeholders
- Operationally meaningful command today is `ingest-flow-help` guidance to run the Metaflow ingestion flow

#### API
File: `src/api/app.py`

What exists:
- FastAPI app
- `/health` endpoint returning `{"status": "ok"}`

Reality:
- No production ATS feature endpoints yet.

### 7) Extraction, Retrieval, Ranking Boundaries
Status: `Scaffold/Placeholder`

Files:
- `src/extract/service.py`
- `src/retrieval/service.py`
- `src/ranking/service.py`

Current state:
- Boundary interfaces and data types are defined
- Most methods raise `NotImplementedError` or return placeholder output

Why this matters:
- Interface-first contracts are present; core business behavior for these stages remains to be implemented.

## Batch Orchestration and Runtime Data Flow
Current end-to-end functional path:

`PDF files` -> `parser` -> `identity resolution` -> `candidate/resume/section persistence` -> `Metaflow run report`

This is the main working vertical slice in the system today.

## Testing Strategy and Protected Contracts

### Unit Coverage (Selected)
- `tests/test_config.py`: settings defaults/shape
- `tests/test_models.py`: ORM table registration
- `tests/test_cli.py`: command wiring visibility
- `tests/test_llm_registry.py`: alias registry load/error behavior
- `tests/test_litellm_client.py`: structured parsing, metadata, embeddings, provider error mapping
- `tests/test_llm_errors.py`: exception coercion taxonomy
- `tests/test_ingest_parser.py`: parser extraction, mapping, diagnostics, language/link behavior
- `tests/test_identity_resolution.py`: email/phone normalization, identity key stability, fallback behavior
- `tests/test_ingest_service.py`: discovery, dedupe, identity reuse, link merging, section routing metadata
- `tests/test_ingest_flow_metrics.py`: telemetry summaries/mutator behavior
- `tests/test_model_fallback.py`: fallback resolver error coercion behavior
- `tests/test_extract_types.py`, `tests/test_ranking_types.py`: type-contract shape checks

### Integration Coverage
Under `tests/integration/` with marker `integration`:
- DB-backed ingestion service behavior
- flow run report smoke behavior
- candidate identity reuse and skip paths

Runtime caveat:
- Integration suite expects Docker/testcontainers availability.

## Developer Runbook

### Setup
```bash
uv sync --all-extras --dev
cp .env.example .env
```

### Migrations
```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head --sql
```

### Tests
```bash
uv run pytest -q
uv run pytest -q -m integration
```

### CLI and API
```bash
uv run ats --help
uv run uvicorn src.api.app:app --reload
```

### Ingestion Flow
```bash
uv run python src/ingest/pdf_ingestion_flow.py run --input-dir data --pattern '*.pdf'
```

### Backfill Utilities
```bash
uv run python scripts/backfill_identity.py
uv run python scripts/backfill_identity.py --apply
uv run python scripts/backfill_candidate_identity_v2.py --dry-run
uv run python scripts/backfill_candidate_identity_v2.py --apply
```

## Stage Status Matrix (Reconciled)
This matrix reconciles `docs/` + reengineering-plan history with current code.

| Stage | Planned intent | Current code reality |
|---|---|---|
| Stage 0 | Foundation/hygiene | Implemented |
| Stage 1 | Durable schema/persistence | Implemented |
| Stage 2 | Provider-agnostic LLM layer | Core implemented; partially integrated |
| Stage 3 | Ingestion/extraction pipeline hardening | Ingestion vertical slice implemented; extraction service layer still partial |
| Stage 4 | Retrieval + hybrid ranking | Pending (contracts only) |
| Stage 5 | Explanations/interview prep | Pending |
| Stage 6 | API expansion + ops hardening | Pending |

## Reality vs Plan Notes
- Older stage docs/plans describe Stage 2 as lacking async/fallback/metadata; current code now includes async methods, alias-based fallback policy, and call metadata types.
- Some docs historically labeled Stage 3 as partially implemented. Current code supports substantial ingestion capabilities, but extraction/retrieval/ranking business stages are still incomplete.
- The canonical source for current behavior is code + tests, not historical plan status labels.

## Public Interfaces and Contracts (Current)

### CLI Contract
- `ats ingest PATH` (placeholder behavior)
- `ats index` (placeholder behavior)
- `ats rank JOB_ID --top-k N` (placeholder behavior)
- `ats ingest-flow-help` (operational helper)

### API Contract
- `GET /health` -> `{"status": "ok"}`

### Ingestion Service Contract
- `IngestionService.discover_pdf_files(input_dir, pattern="*.pdf") -> list[Path]`
- `IngestionService.parse_pdf(path) -> ParsedResume`
- `IngestionService.ingest_pdf(path, session) -> IngestionResult`

### LLM Contract
- `LLMClient.generate_structured(...)`
- `LLMClient.embed(...)`
- async variants and metadata-returning variants

## Current Gaps and Risks
- `extract`, `retrieval`, and `ranking` services are mostly stubs.
- CLI/API are mostly scaffolding beyond health and flow guidance.
- Alias config must stay aligned with available provider models to avoid runtime failures.
- System-level observability and production ops hardening are early-stage.

## Legacy Appendix (Historical, Not Active Architecture)
Legacy code under `thereisnohr/` contains the old pipeline (`pipeline/main.py`, selector, profiler, data handlers).

Reused concepts in new architecture:
- PDF markdown extraction patterns
- some cleaning/parsing ideas

Not reused as primary runtime:
- file-append summary workflow
- tightly coupled legacy pipeline orchestration

For new development, use `src/` architecture only.

## Source References Used for This Guide

### Docs
- `docs/architecture.md`
- `docs/stage-0-1-guide.md`
- `docs/stage-2-llm.md`
- `docs/stage-3-ingestion.md`

### Plans
- `.plans/REENGINEERING_PLAN.md`

### Code Anchors
- `src/core/*`
- `src/storage/*`
- `src/llm/*`
- `src/ingest/*`
- `src/extract/*`
- `src/retrieval/*`
- `src/ranking/*`
- `src/cli.py`
- `src/api/app.py`
- `alembic/versions/*`
- `config/model_aliases.yaml`
- `scripts/*`
- `tests/*`
