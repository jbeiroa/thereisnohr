"""Ranking-layer services and schemas for candidate ordering and explanations."""

from dataclasses import dataclass

from src.llm.client import LLMClient
from src.llm.factory import build_default_llm_client
from src.ranking.types import (
    InterviewPrepPack,
    RankedCandidate,
    RankExplanation,
    RankInput,
    ScoreBreakdown,
)


@dataclass
class RankingService:
    """Service object that orchestrates ranking workflow operations."""

    llm_client: LLMClient | None = None
    ranker_model_alias: str = "ranker_default"

    def _resolve_llm_client(self) -> LLMClient:
        """Returns an LLM client instance."""
        if self.llm_client is not None:
            return self.llm_client
        return build_default_llm_client()

    def rank_candidates(self, inputs: list[RankInput], top_k: int = 5) -> list[RankedCandidate]:
        """Rank structured candidate inputs and return ranked candidate outputs."""
        scored: list[RankedCandidate] = []
        for inp in inputs:
            breakdown = self._deterministic_score(inp)
            scored.append(
                RankedCandidate(
                    candidate_id=inp.candidate_id,
                    rank=0,  # Placeholder
                    scores=breakdown,
                )
            )

        # Sort by deterministic score descending
        scored.sort(key=lambda x: x.scores.final_score, reverse=True)

        # Rerank top-N with LLM
        top_n = scored[:top_k]
        if top_n:
            reranked_results = self._rerank_with_llm(top_n, inputs)
            for candidate, (adjustment, explanation) in zip(top_n, reranked_results):
                candidate.scores.llm_adjustment = adjustment
                candidate.scores.final_score += adjustment
                candidate.explanation = explanation
                if explanation:
                    inp = next(x for x in inputs if x.candidate_id == candidate.candidate_id)
                    candidate.interview_pack = self.generate_interview_pack(inp, explanation)

        # Re-sort after adjustment
        scored.sort(key=lambda x: x.scores.final_score, reverse=True)

        # Assign final ranks
        for i, candidate in enumerate(scored, 1):
            candidate.rank = i

        return scored

    def _deterministic_score(self, rank_input: RankInput) -> ScoreBreakdown:
        """Compute deterministic score components for one rank input.

        Logic:
        - Base score is retrieval_score (normalized to 0-1 range).
        - Skill overlap: +0.1 per matched hard skill, up to 0.5.
        - Experience match: (TBD).
        """
        req_skills = {s.lower() for s in rank_input.requirements.hard_skills}
        cand_skills = {s.lower() for s in rank_input.signals.skills}

        matched = list(req_skills & cand_skills)
        missing = list(req_skills - cand_skills)

        # Heuristic: 50% vector retrieval, 50% skill overlap
        retrieval_weight = 0.5
        skill_weight = 0.5

        skill_score = len(matched) / len(req_skills) if req_skills else 1.0

        final_score = (rank_input.retrieval_score * retrieval_weight) + (skill_score * skill_weight)

        return ScoreBreakdown(
            deterministic_score=final_score,
            final_score=final_score,
            matched_hard_skills=matched,
            missing_hard_skills=missing,
        )

    def _rerank_with_llm(
        self,
        top_candidates: list[RankedCandidate],
        all_inputs: list[RankInput],
    ) -> list[tuple[float, RankExplanation | None]]:
        """Optionally rerank top candidates with LLM-generated adjustments/explanations."""
        results: list[tuple[float, RankExplanation | None]] = []
        client = self._resolve_llm_client()
        from src.core.logging import get_run_logger

        log = get_run_logger(__name__)

        # Map inputs for easy lookup
        input_map = {inp.candidate_id: inp for inp in all_inputs}

        for cand in top_candidates:
            inp = input_map[cand.candidate_id]
            prompt = (
                "Evaluate the fit of this candidate for the job based on the extracted requirements and candidate signals.\n"
                "Provide a human-readable, evidence-based summary. For each strength, cite a short quote from the candidate signals. "
                "For gaps and risks, identify missing requirements, assess the impact, and provide a hint for how to clarify this uncertainty in an interview.\n"
                "Finally, provide an `llm_adjustment_score` between -0.2 (poor qualitative fit) and +0.2 (excellent qualitative fit) "
                "to adjust the initial deterministic match score based on your holistic assessment.\n\n"
                f"Job Requirements:\n{inp.requirements.model_dump_json(indent=2)}\n\n"
                f"Candidate Signals:\n{inp.signals.model_dump_json(indent=2)}\n\n"
                "Return valid JSON matching the requested schema."
            )

            try:
                explanation = client.generate_structured(
                    prompt=prompt,
                    schema=RankExplanation,
                    model_alias=self.ranker_model_alias,
                )
                # Use the adjustment score from the LLM
                adjustment = explanation.llm_adjustment_score if explanation else 0.0
                results.append((adjustment, explanation))
            except Exception as e:
                log.error(f"Failed reranking for candidate {cand.candidate_id}: {e}")
                results.append((0.0, None))

        return results

    def generate_interview_pack(
        self, rank_input: RankInput, explanation: RankExplanation
    ) -> InterviewPrepPack | None:
        """Generate tailored interview preparation questions for a candidate."""
        client = self._resolve_llm_client()
        from src.core.logging import get_run_logger

        log = get_run_logger(__name__)

        prompt = (
            "You are an expert technical interviewer. Generate a high-quality interview preparation pack for a candidate. "
            "Your goal is to provide specific, challenging questions that help evaluate the candidate's fit for the role.\n\n"
            "Requirements:\n"
            "1. technical_questions: Generate 3-5 specific questions about the candidate's core technical skills and how they applied them in their experience.\n"
            "2. behavioral_questions: Generate 2-3 questions about their past experience highlights and soft skills.\n"
            "3. clarification_questions: Generate specific questions to address the 'gaps_and_risks' identified in the ranking explanation. Help the interviewer resolve these uncertainties.\n\n"
            f"Job Requirements:\n{rank_input.requirements.model_dump_json(indent=2)}\n\n"
            f"Candidate Signals:\n{rank_input.signals.model_dump_json(indent=2)}\n\n"
            f"Candidate Ranking Explanation:\n{explanation.model_dump_json(indent=2)}\n\n"
            "Return valid JSON matching the requested schema. Ensure all question lists are populated with detailed, tailored questions. Do not return empty lists."
        )

        try:
            return client.generate_structured(
                prompt=prompt,
                schema=InterviewPrepPack,
                model_alias="explainer_default",
            )
        except Exception as e:
            log.error(
                f"Failed to generate interview pack for candidate {rank_input.candidate_id}: {e}"
            )
            return None
