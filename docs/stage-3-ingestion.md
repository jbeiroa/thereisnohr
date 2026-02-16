# Stage 3 (Start): PDF Ingestion Pipeline with Metaflow

This document covers the first Stage 3 implementation slice: ingesting PDF resumes, parsing them, and persisting records into Postgres using Metaflow orchestration.

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

## 2) What was implemented now

- `src/ingest/parser.py`
  - PDF -> markdown extraction
  - cleaned text + link extraction
  - markdown heading-based section extraction
  - lightweight language detection
- `src/ingest/types.py`
  - `ParsedResume` model
- `src/ingest/service.py`
  - PDF discovery
  - parse + persist to DB (`candidates`, `resumes`, `resume_sections`)
  - duplicate-skip behavior by `resumes.source_file`
- `src/ingest/pdf_ingestion_flow.py`
  - Metaflow `FlowSpec` for batch orchestration (`discover -> foreach ingest -> join`)
- `src/storage/repositories.py`
  - added candidate external-id dedup helpers
  - added resume lookup and richer create fields
  - added `ResumeSectionRepository`

## 3) Persistence behavior

For each PDF:

1. Candidate
- External ID is derived deterministically from file path hash.
- Candidate record is upserted by `external_id`.

2. Resume
- Stored with full raw markdown text in `resumes.raw_text`.
- Parsed artifacts stored in `resumes.parsed_json`:
  - `clean_text`
  - `links`
  - `parser_version`
  - `section_names`
- Language stored in `resumes.language`.

3. Resume sections
- One row per extracted section in `resume_sections`.
- Includes token count and parser version metadata.

## 4) How to run the flow

```bash
uv run python src/ingest/pdf_ingestion_flow.py run --input-dir data --pattern '*.pdf'
```

CLI helper:

```bash
uv run ats ingest-flow-help
```

## 5) Current constraints

- Candidate identity currently inferred from file name/path hash (temporary heuristic).
- No OCR fallback yet for scanned PDFs.
- No advanced section normalization yet (that comes in later Stage 3/4 increments).
- Metaflow execution is local process mode by default.

## 6) Next expected Stage 3 increments

1. Stronger candidate identity extraction (email/phone/name from content).
2. Better section taxonomy normalization (experience/education/skills mapping).
3. Idempotent ingestion via content hash (not only source file path).
4. Ingestion metrics and structured run-level telemetry.
