# Stage 3 (In Progress): PDF Ingestion Pipeline with Metaflow

This document covers the current Stage 3 implementation state: PDF ingestion, parser hardening work, and persistence into Postgres using Metaflow orchestration.

## 1) Legacy reuse analysis

The pre-reengineering code under `thereisnohr/` was analyzed for reuse.

### Reused partially

1. `thereisnohr/data/getter.py`
- Reused concept: `pymupdf4llm.to_markdown(...)` as the PDF extraction primitive.
- New location: `src/ingest/parser.py::extract_markdown`.
- Why partial reuse: old `Getter` mixed file iteration and extraction state. New implementation separates concerns for pipeline orchestration and DB persistence.

2. `thereisnohr/data/handler.py`
- Reused concept: block splitting, deduplication, and link extraction.
- New location: `src/ingest/parser.py::split_by_blocks` and `clean_resume_blocks`.
- Why partial reuse: old cleaning dropped too much useful content (year/location filters) and had an uninitialized return-path risk. New parser keeps conservative cleaning.

### Not reused directly

1. `thereisnohr/pipeline/main.py`
- Not reused: tight coupling to local files and append-only text outputs (`summary.txt`).
- Replacement: Metaflow orchestration + DB-backed ingestion records.

2. Legacy summarization/selection path
- Not part of Stage 3 ingestion scope. Preserved as historical reference until replaced by Stage 4+.

## 2) What is implemented

- `src/ingest/parser.py`
  - PDF -> markdown extraction
  - markdown precleaning helpers to remove conversion artifacts
  - cleaned text + link extraction
  - heading span detection and canonical section mapping
  - section absorption rule for noisy heading output:
    - consecutive `general` spans are absorbed into the previous single-line non-`general` section
  - parser outputs both:
    - `sections: dict[str, str]`
    - `section_items: list[SectionItem]`
  - lightweight language detection
- `src/ingest/entities.py`
  - `ParsedResume`, `HeadingSpan`, `SectionItem`
- `src/ingest/service.py`
  - PDF discovery
  - parse + persist to DB (`candidates`, `resumes`, `resume_sections`)
  - duplicate-skip behavior by `resumes.source_file` and `resumes.content_hash`
- `src/ingest/pdf_ingestion_flow.py`
  - Metaflow `FlowSpec` for batch orchestration (`discover -> foreach ingest -> join`)
  - flow-level run report artifact (`run_report`) with status/timing/quality metrics
  - styled card reporting in `end` step (`run_metrics`)
- `src/storage/repositories.py`
  - added candidate external-id dedup helpers
  - added resume lookup and richer create fields
  - added `ResumeSectionRepository`
- Notebook experimentation suite under `notebooks/`
  - `parsers_testing.ipynb`
  - `ingestion_service_testing.ipynb`
  - `repositories_smoke_testing.ipynb`
  - `llm_registry_testing.ipynb`
  - `notebooks/README.md`

## 3) Persistence behavior

For each PDF:

1. Candidate
- External ID is derived deterministically from content identity signals (`email`, `phone`, `name`) as `candidate:v1:*`.
- Candidate record is upserted by `external_id`.
- Fallback identity for resumes with no detectable signals uses `resume_content:*`.

2. Resume
- Stored with full raw markdown text in `resumes.raw_text`.
- Content hash stored in `resumes.content_hash` for idempotency.
- Parsed artifacts stored in `resumes.parsed_json`:
  - `clean_text`
  - `links`
  - `parser_version`
  - `section_names`
  - `identity` (resolved signals + confidence + diagnostics)
- Language stored in `resumes.language`.

3. Resume sections
- One row per extracted section in `resume_sections`.
- Includes token count and parser version metadata.
- Includes confidence/diagnostic metadata (`section_confidence`, flags, recategorization candidate).

4. Flow run report (`run_report` artifact in `end` step)
- `run_meta`: run id/timestamps/input parameters + discovery metadata.
- `status_counts`: counts by result status.
- `step_timing_summary`: per-step latency stats (`p50/p95/max`) + error counts.
- `ingest_quality`: identity and section confidence summaries.
- `reason_breakdown`: skip reasons and grouped error types.
- `files`: per-file outcomes (full) + sampled subset for card rendering.

Parser entity contract also includes richer in-memory output used for experimentation:
- `ParsedResume.sections`
- `ParsedResume.section_items`
- `ParsedResume.links`

## 4) How to run the flow

```bash
uv run python src/ingest/pdf_ingestion_flow.py run --input-dir data --pattern '*.pdf'
```

CLI helper:

```bash
uv run ats ingest-flow-help
```

Flow run now emits:
- console summary (`ingested/skipped/errors`),
- `run_report` artifact in flow `end` step,
- `run_metrics` card with styled KPI/report view.

Backfill utility (dry-run by default):

```bash
uv run python scripts/backfill_identity.py
uv run python scripts/backfill_identity.py --apply
```

## 5) Current constraints

- Optional model-based NER fallback is not enabled by default (rules-first extraction only).
- Section diagnostics are persisted, but recategorization remains advisory metadata only.
- OCR fallback for scanned PDFs is currently de-prioritized and out of active Stage 3 scope.
- Metaflow execution is local process mode by default.

## 6) Tests and validation

Current automated coverage includes:

- parser unit tests for section extraction, bilingual heading mapping, and link extraction.
- parser rule coverage for absorption behavior (single-line non-`general` section absorbs following `general` spans).
- ingestion service helper tests for file discovery and deterministic candidate external-id generation.

Current notebook coverage includes:

- parser QA notebook with assertion-driven checks (`notebooks/parsers_testing.ipynb`),
- service/repository/registry smoke notebooks for isolated experimentation.

## 7) Next expected Stage 3 increments

1. Optional model-based fallback for low-confidence name extraction (Presidio/HF/GLiNER adapter).
2. DB-backed integration tests for end-to-end ingestion validation (identity/idempotency/reporting).
