"""Ranking-layer services and schemas for candidate ordering and explanations."""

from dataclasses import dataclass

from src.llm.client import LLMClient
from src.llm.factory import build_default_llm_client
from src.ranking.types import RankedCandidate, RankExplanation, RankInput, ScoreBreakdown


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

    def rank_candidates(self, inputs: list[RankInput]) -> list[RankedCandidate]:
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
        top_n = scored[:5]
        if top_n:
            reranked_results = self._rerank_with_llm(top_n, inputs)
            for candidate, (adjustment, explanation) in zip(top_n, reranked_results):
                candidate.scores.llm_adjustment = adjustment
                candidate.scores.final_score += adjustment
                candidate.explanation = explanation

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
                "Provide a human-readable explanation and an adjustment score between -0.2 and 0.2.\n\n"
                f"Job Requirements: {inp.requirements.model_dump_json()}\n"
                f"Candidate Signals: {inp.signals.model_dump_json()}\n"
                "Return JSON matching the schema."
            )
            
            try:
                explanation = client.generate_structured(
                    prompt=prompt,
                    schema=RankExplanation,
                    model_alias=self.ranker_model_alias,
                )
                # For now, we stub the adjustment as 0.0 unless we want to extend RankExplanation to include a score.
                # Let's assume the LLM just provides the qualitative explanation for now.
                results.append((0.0, explanation))
            except Exception as e:
                log.error(f"Failed reranking for candidate {cand.candidate_id}: {e}")
                results.append((0.0, None))
                
        return results
