"""Application module `src.ranking.service`."""

from dataclasses import dataclass

from src.ranking.types import RankInput, RankedCandidate, RankExplanation, ScoreBreakdown


@dataclass
class RankingService:
    """Represents RankingService."""

    def rank(self, candidate_ids: list[int]) -> list[int]:
        """Run rank.

        Args:
            candidate_ids: Input parameter.

        Returns:
            object: Computed result.

        """
        return candidate_ids

    def rank_candidates(self, inputs: list[RankInput]) -> list[RankedCandidate]:
        """Rank structured candidate inputs and return ranked candidate outputs."""
        _ = inputs
        raise NotImplementedError("Candidate ranking is not implemented yet.")

    def _deterministic_score(self, rank_input: RankInput) -> ScoreBreakdown:
        """Compute deterministic score components for one rank input."""
        _ = rank_input
        raise NotImplementedError("Deterministic scoring is not implemented yet.")

    def _rerank_with_llm(
        self,
        ranked: list[RankedCandidate],
    ) -> list[tuple[float, RankExplanation | None]]:
        """Optionally rerank top candidates with LLM-generated adjustments/explanations."""
        _ = ranked
        raise NotImplementedError("LLM reranking is not implemented yet.")
