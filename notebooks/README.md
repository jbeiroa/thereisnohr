# Notebooks (Stage 3 Experimentation)

This folder contains non-legacy notebooks for isolated experimentation and smoke validation.

## Execution order
1. `ingestion_service_testing.ipynb`
2. `repositories_smoke_testing.ipynb`
3. `llm_registry_testing.ipynb`

## Notebook purposes
- `ingestion_service_testing.ipynb`: service-level checks without Metaflow, including deterministic identity extraction/content-hash checks and section diagnostics inspection.
- `repositories_smoke_testing.ipynb`: repository persistence smoke checks against dev DB, including identity-key upsert and content-hash roundtrip behavior.
- `llm_registry_testing.ipynb`: alias registry checks, plus optional credential-gated live calls.

## Prerequisites
- Python env with project dependencies.
- Run notebooks from repository root so `Path.cwd()` resolves correctly.
- PDFs available under `data/` for parser/ingestion notebooks.
- Local DB running and migrated for repository smoke notebook.
- Optional provider credentials (for live LLM checks).

## Pass criteria
- Ingestion service notebook: discovery ordering, parse-through-service assertions, deterministic identity/content-hash checks, and section diagnostics assertions pass.
- Repository notebook: candidate identity-key idempotency, resume source/content-hash roundtrip, and section diagnostics metadata persistence assertions pass.
- LLM registry notebook: expected aliases resolve, unknown alias path raises expected error, live checks optional.

## Troubleshooting
- Missing kernel/import path:
  - Ensure Jupyter uses the same environment as `uv run`.
  - Run notebook from repo root.
- DB connection errors:
  - Verify `DATABASE_URL` and local DB availability.
  - Confirm migrations are applied.
- Missing LLM credentials:
  - Set required env vars (for example `OPENAI_API_KEY`) before running optional live cells.

## Legacy note
`legacy/` is archival from the previous project version and is intentionally unmanaged by this notebook suite.
