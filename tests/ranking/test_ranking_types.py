"""Tests for ranking type scaffolding."""

from src.ranking.types import RankedCandidate, RankExplanation, ScoreBreakdown


def test_ranking_type_shape() -> None:
    """Verify ranking models instantiate with expected minimal shape."""
    breakdown = ScoreBreakdown(deterministic_score=0.7, final_score=0.7)
    explanation = RankExplanation(summary="placeholder")
    row = RankedCandidate(candidate_id=1, rank=1, scores=breakdown, explanation=explanation)
    assert row.candidate_id == 1
    assert row.scores.final_score == 0.7
