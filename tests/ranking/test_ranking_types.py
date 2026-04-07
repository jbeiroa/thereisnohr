"""Tests for ranking type scaffolding."""

from src.ranking.types import RankedCandidate, RankExplanation, ScoreBreakdown, StrengthWithEvidence, GapOrRisk, InterviewPrepPack


def test_ranking_type_shape() -> None:
    """Verify ranking models instantiate with expected minimal shape."""
    breakdown = ScoreBreakdown(deterministic_score=0.7, final_score=0.7)
    
    strength = StrengthWithEvidence(skill_or_trait="Python", resume_evidence_quote="Built APIs in Python.")
    gap = GapOrRisk(missing_requirement="SQL", impact="Moderate", uncertainty_hint="Ask about db experience.")
    
    explanation = RankExplanation(
        evidence_based_summary="Good candidate.",
        strengths_with_evidence=[strength],
        gaps_and_risks=[gap]
    )
    
    row = RankedCandidate(candidate_id=1, rank=1, scores=breakdown, explanation=explanation)
    assert row.candidate_id == 1
    assert row.scores.final_score == 0.7

def test_interview_prep_pack_shape() -> None:
    """Verify InterviewPrepPack instantiates correctly."""
    pack = InterviewPrepPack(
        technical_questions=["How would you structure a FastAPI app?"],
        behavioral_questions=["Tell me about a time you led a team."],
        clarification_questions=["Can you elaborate on your SQL experience?"]
    )
    assert len(pack.technical_questions) == 1
