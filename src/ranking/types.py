"""Ranking-layer services and schemas for candidate ordering and explanations."""

from pydantic import BaseModel, Field

from src.extract.types import CandidateSignals, JobRequirements


class RankInput(BaseModel):
    """Input payload for candidate ranking."""

    candidate_id: int
    retrieval_score: float
    requirements: JobRequirements
    signals: CandidateSignals


class ScoreBreakdown(BaseModel):
    """Detailed score components for explainable ranking."""

    deterministic_score: float
    llm_adjustment: float = 0.0
    final_score: float
    matched_hard_skills: list[str] = Field(default_factory=list)
    missing_hard_skills: list[str] = Field(default_factory=list)


class StrengthWithEvidence(BaseModel):
    """Specific strength identified with a quote from the candidate's resume."""

    skill_or_trait: str
    resume_evidence_quote: str


class GapOrRisk(BaseModel):
    """Specific missing requirement or risk factor identified."""

    missing_requirement: str
    impact: str
    uncertainty_hint: str


class RankExplanation(BaseModel):
    """Human-readable rationale for the assigned score."""

    evidence_based_summary: str
    strengths_with_evidence: list[StrengthWithEvidence] = Field(default_factory=list)
    gaps_and_risks: list[GapOrRisk] = Field(default_factory=list)
    llm_adjustment_score: float = Field(
        default=0.0,
        description="A score adjustment between -0.2 (poor qualitative fit) and +0.2 (excellent qualitative fit) based on qualitative assessment.",
    )


class InterviewPrepPack(BaseModel):
    """Interview questions tailored to candidate fit and gaps."""

    technical_questions: list[str] = Field(
        default_factory=list,
        description="3-5 deep technical questions about the candidate's core skills and experience.",
    )
    behavioral_questions: list[str] = Field(
        default_factory=list,
        description="2-3 questions about the candidate's soft skills and work history.",
    )
    clarification_questions: list[str] = Field(
        default_factory=list,
        description="Specific questions to clarify the gaps or risks identified in the ranking explanation.",
    )


class RankedCandidate(BaseModel):
    """Ranked output record for one candidate."""

    candidate_id: int
    rank: int
    scores: ScoreBreakdown
    explanation: RankExplanation | None = None
    interview_pack: InterviewPrepPack | None = None
