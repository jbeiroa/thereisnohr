# Stage 0/1 Implementation Guide

This guide documents how to use and reason about the new Stage 0/1 code paths.

## 1) Prerequisites

- Python 3.12+
- `uv` installed
- PostgreSQL 14+ (with ability to install `vector` extension)

## 2) Local setup

```bash
cd /tmp/thereisnohr-main
uv sync --all-extras --dev
cp .env.example .env
```

Edit `.env` for your local DB URL if needed.

## 3) Database initialization

Generate/apply schema:

```bash
uv run alembic upgrade head
```

Check migration SQL without executing:

```bash
uv run alembic upgrade head --sql
```

## 4) Verify baseline health

Run tests:

```bash
uv run pytest -q
```

Run CLI help:

```bash
uv run ats --help
```

Run API health endpoint:

```bash
uv run uvicorn src.api.app:app --reload
# then GET /health
```

Expected response:

```json
{"status":"ok"}
```

## 5) Current functional behavior by command

## `ats ingest PATH`

Current behavior:

- validates command wiring and logs a run-scoped event,
- prints placeholder text.

Intended future behavior:

- accept file(s), extract raw text, normalize metadata, persist `candidate` + `resume` records.

## `ats index`

Current behavior:

- validates command wiring and logs a run-scoped event,
- prints placeholder text.

Intended future behavior:

- parse resumes into sections, generate embeddings, persist vectors and metadata.

## `ats rank JOB_ID --top-k N`

Current behavior:

- validates command wiring and logs a run-scoped event,
- prints placeholder text with parameters.

Intended future behavior:

- retrieve candidates, apply hybrid scoring, persist match rows, return top-k with reasons.

## 6) Python usage examples (current)

## Load typed settings

```python
from src.core.config import get_settings

settings = get_settings()
print(settings.database_url)
```

Why:

- one source of configuration truth,
- avoids hard-coded runtime values.

## Create DB session and repositories

```python
from src.storage.db import get_session
from src.storage.repositories import CandidateRepository, JobPostingRepository

session = get_session()
try:
    c_repo = CandidateRepository(session)
    j_repo = JobPostingRepository(session)

    candidate = c_repo.create(name="Ada Lovelace", email="ada@example.com")
    job = j_repo.create(
        title="Physics Teacher",
        description="Teach physics and run laboratory sessions.",
    )

    session.commit()
    print(candidate.id, job.id)
finally:
    session.close()
```

Why repositories:

- keeps DB access patterns centralized,
- simplifies future transaction and query policy changes.

## 7) Data model intent and usage patterns

## `candidates`

Stores canonical applicant identity/contact. One candidate can have multiple resume versions.

## `resumes`

Stores immutable source text + parsed JSON. Allows re-extraction/re-indexing without re-upload.

## `resume_sections`

Stores normalized sections for fine-grained retrieval and evidence extraction.

## `embeddings`

Stores vectors with model metadata and text hash for dedup/recompute logic.

## `matches`

Stores ranking outcomes and reasons for reproducibility and recruiter audits.

## `job_postings`

Stores role definition and structured requirement payloads used in matching.

## 8) Design decisions and rationale

1. Persist before optimize
- Durable schema first ensures future ranking/extraction experiments are reproducible.

2. Explicit module boundaries
- Ingest/extract/retrieve/rank modules isolate concerns and reduce coupling.

3. Placeholders as contract anchors
- CLI and service stubs intentionally lock interface shape before heavy logic lands.

4. Migration-first DB workflow
- Alembic revisions are part of normal development, not an afterthought.

5. Flat `src/` for iteration speed
- Keeps the code easy to navigate while domain model stabilizes.

## 9) Known limitations in Stage 0/1

- No production ingestion/extraction implementation yet.
- No provider-agnostic LLM adapter yet (planned Stage 2 with LiteLLM).
- No retrieval/ranking scoring logic yet.
- No end-user API surface yet beyond healthcheck.

These are deliberate: this stage secures the foundation before introducing model and ranking complexity.

## 10) Recommended current workflow for contributors

1. Sync env: `uv sync --all-extras --dev`
2. Run tests: `uv run pytest -q`
3. Add/modify schema via Alembic migration
4. Extend one service boundary at a time (`ingest`, then `extract`, etc.)
5. Add tests for each boundary before wiring into CLI/API

This keeps evolution incremental and avoids regressions during Stage 2 integration.
