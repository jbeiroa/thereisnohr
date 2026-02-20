# Notebooks (Stage 3 Experimentation)

This folder contains non-legacy notebooks for isolated experimentation and smoke validation.

## Execution order
1. `parsers_testing.ipynb`
2. `ingestion_service_testing.ipynb`
3. `repositories_smoke_testing.ipynb`
4. `llm_registry_testing.ipynb`

## Notebook purposes
- `parsers_testing.ipynb`: parser QA (precleaning, heading spans, canonical mapping, absorption behavior, links).
- `ingestion_service_testing.ipynb`: service-level checks without Metaflow.
- `repositories_smoke_testing.ipynb`: repository persistence smoke checks against dev DB.
- `llm_registry_testing.ipynb`: alias registry checks, plus optional credential-gated live calls.

## Prerequisites
- Python env with project dependencies.
- Run notebooks from repository root so `Path.cwd()` resolves correctly.
- PDFs available under `data/` for parser/ingestion notebooks.
- Local DB running and migrated for repository smoke notebook.
- Optional provider credentials (for live LLM checks).

## Pass criteria
- Parser notebook: absorption and link extraction assertions pass; section output is sensible for selected samples.
- Ingestion service notebook: discovery ordering, deterministic helper checks, and parse-through-service assertion pass.
- Repository notebook: candidate idempotency, resume roundtrip, and section persistence assertions pass.
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
