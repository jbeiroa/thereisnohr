"""Ranking-layer services and schemas for candidate ordering and explanations."""

from dataclasses import dataclass

from src.ranking.types import RankInput, RankedCandidate, RankExplanation, ScoreBreakdown


@dataclass
class RankingService:
    """Service object that orchestrates ranking workflow operations."""

    def rank(self, candidate_ids: list[int]) -> list[int]:
        """Runs rank logic.

        Args:
            candidate_ids (list[int]): Input value used by `candidate_ids`.

        Returns:
            list[int]: Ordered list produced by this operation.
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
