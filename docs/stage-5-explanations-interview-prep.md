# Stage 5 (Completed): Explanations and Interview Preparation

This document covers the Stage 5 implementation: evidence-based ranking explanations and automated interview preparation packs.

## 1) Grounded Match Explanations

The ranking process now produces qualitative rationales that are explicitly grounded in the candidate's resume content.

- **Schema:** `RankExplanation`.
- **Fields:**
  - `evidence_based_summary`: A high-level qualitative assessment.
  - `strengths_with_evidence`: A list of skills or traits, each paired with a direct quote from the resume (`resume_evidence_quote`).
  - `gaps_and_risks`: Identification of missing requirements, their impact on the role, and an `uncertainty_hint` for the recruiter to probe.
- **Implementation:** `RankingService._rerank_with_llm` uses a specialized prompt to enforce evidence extraction using the `ranker_default` model alias (`gpt-4o-mini`).

## 2) Automated Interview Preparation

The ATS now generates tailored interview questions for top candidates to help recruiters validate the match.

- **Storage:** `matches.interview_pack_json`.
- **Content:**
  - `technical_questions`: Probes mastery of required hard skills.
  - `behavioral_questions`: Probes soft skills and past experience highlights.
  - `clarification_questions`: Specifically targets the "gaps and risks" identified during ranking to resolve uncertainties.
- **Automation:** The `RankingWorkflow` automatically generates prep packs for the **Top 3 candidates** during every `ats rank` execution.

## 3) CLI Integration

Two main entry points interact with Stage 5 features:

### Enhanced Ranking Output
```bash
uv run ats rank <job_id>
```
Displays the evidence-based summary and a preview of gaps/risks for all ranked candidates.

### Dedicated Preparation Command
```bash
uv run ats prep <job_id> <candidate_id>
```
Retrieves and displays the full interview preparation pack. If the pack hasn't been generated yet (e.g., for a candidate outside the top 3), it generates it on-the-fly and persists it to the database.

## 4) Persistence & Schema Changes

- **Migration:** Added `interview_pack_json` (JSONB) to the `matches` table.
- **Repository:** Updated `MatchRepository` to handle the new field.

## 5) Testing and Validation

- **Unit Tests:** Updated `tests/ranking/test_ranking_types.py` to validate the new Pydantic schemas for explanations and prep packs.
- **Integration Tests:** Added `tests/integration/test_match_repository.py` to ensure JSON payloads are correctly persisted and retrieved from Postgres.
- **LLM Reliability:** Improved `LiteLLMClient` system prompts to ensure the LLM consistently populates structured lists instead of returning empty objects.
