"""Application module `src.ranking.types`."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.extract.types import CandidateSignals, JobRequirements


class RankInput(BaseModel):
    """Input payload for candidate ranking."""

    candidate_id: int
    requirements: JobRequirements
    signals: CandidateSignals


class ScoreBreakdown(BaseModel):
    """Detailed score components for explainable ranking."""

    deterministic_score: float
    llm_adjustment: float = 0.0
    final_score: float
    matched_hard_skills: list[str] = Field(default_factory=list)
    missing_hard_skills: list[str] = Field(default_factory=list)


class RankExplanation(BaseModel):
    """Human-readable rationale for the assigned score."""

    summary: str
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class RankedCandidate(BaseModel):
    """Ranked output record for one candidate."""

    candidate_id: int
    rank: int
    scores: ScoreBreakdown
    explanation: RankExplanation | None = None
