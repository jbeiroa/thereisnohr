# Stage 4 (Completed): Retrieval and Hybrid Ranking

This document covers the Stage 4 implementation: job requirement parsing, vector retrieval, deterministic scoring, and LLM-based reranking.

## 1) Job Posting Ingestion

The ATS now supports ingesting Job Descriptions (JDs) with structured requirement extraction.

- **Storage:** `job_postings` table.
- **Fields:** `title`, `description`, `requirements_json`, `created_at`.
- **Extraction:** `ExtractionService.extract_job_requirements` uses an LLM to extract `hard_skills`, `soft_skills`, `years_experience_min`, `education`, and `certifications`.
- **CLI Command:**
  ```bash
  uv run ats ingest-job path/to/jd.txt --title "Senior Software Engineer"
  ```

## 2) Candidate Signal Enrichment

During resume ingestion, the pipeline now performs a secondary LLM extraction to derive structured "signals" from the parsed sections.

- **Storage:** `resumes.signals_json`.
- **Fields:** `skills`, `experience_highlights`, `education`, `certifications`, `summary`.
- **Why?** Raw sections are great for vector search, but structured signals are required for fast, deterministic scoring (e.g., "does this candidate have Python?").
- **Implementation:** `IngestionService.ingest_pdf` now calls `ExtractionService.extract_candidate_signals` and persists the output.

## 3) Hybrid Retrieval & Ranking Pipeline

The ranking process follows a multi-stage "funnel" approach to balance speed and accuracy.

### Stage 1: Vector Retrieval (The Wide Net)
- **Tool:** `RetrievalService.top_k`.
- **Logic:** Uses `pgvector` to find the top-N candidates whose resume sections are semantically similar to the job description.
- **Output:** A list of `(candidate_id, retrieval_score)` tuples.

### Stage 2: Deterministic Scoring (The Filter)
- **Tool:** `RankingService._deterministic_score`.
- **Logic:** Computes a heuristic score (currently 50% vector score + 50% skill overlap). It compares `job.requirements_json` against the candidate's `resume.signals_json`.
- **Output:** A sorted list of `RankedCandidate` objects with a `ScoreBreakdown`.

### Stage 3: LLM Reranking (The Refiner)
- **Tool:** `RankingService._rerank_with_llm`.
- **Logic:** Takes the top-5 candidates from Stage 2 and passes their signals and the job requirements to an LLM for a qualitative assessment.
- **Output:** A `RankExplanation` (summary, strengths, risks) for each candidate.

## 4) Persistence & Results

Ranking results are persisted to the `matches` table for later review or API consumption.

- **Command:**
  ```bash
  uv run ats rank <job_id> --top-k 5
  ```
- **Persisted Data:** `job_id`, `candidate_id`, `retrieval_score`, `rerank_score`, `final_score`, and `reasons_json` (containing the rank, explanation, and score breakdown).
- **Idempotency:** The ranking workflow uses an **upsert strategy**. Rerunning the `rank` command for the same job and candidate updates the existing match record instead of creating duplicates.

## 5) Database and Script Optimizations

As part of Phase 4, the following changes were applied:
- **Dropped `owner_type` from `embeddings`:** Since the ATS currently only embeds `resume_section`s, this column was redundant.
- **Updated Indexes:** Modified `ix_embeddings_owner` and `ix_embeddings_model_dimensions_owner` to reflect the removal of `owner_type`.
- **Maintenance Scripts:** Updated `scripts/backfill_section_embeddings.py`, `scripts/create_embedding_hnsw_indexes.py`, and `scripts/backfill_candidate_identity_v2.py` to remove references to the dropped `owner_type` column and ensure compatibility with the new schema.

## 6) Reliability and Logging

- **Model Aliases:** Added `ranker_default` to `config/model_aliases.yaml`. By default, it uses `openai/gpt-4o-mini` for high-quality, stable qualitative assessments, with local fallbacks.
- **Resilient Configuration:** Increased LLM timeouts to 60 seconds and retries to 3 to handle potential model latency during reranking.
- **Robust Logging:** Implemented a `RunIDFilter` in `src/core/logging.py` to prevent crashes when external libraries (like LiteLLM) emit logs without the required `run_id` field.
- **Unit Tests:** Updated `tests/storage/test_embedding_repository.py` and `tests/ingest/test_ingest_service.py` to reflect schema changes and mock the new LLM extraction calls.
- **CLI Validation:** The `ats ingest-job` and `ats rank` commands provide colored console output for immediate feedback.

## 7) Future Work (Stage 5+)

- **Ranking Heuristics:** Refine the `_deterministic_score` to include years of experience and education level matching.
- **API Endpoints:** Expose the ranking workflow via FastAPI endpoints.
- **Web UI:** Build a dashboard to visualize job postings and their ranked candidate matches.
