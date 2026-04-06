"""Extraction-layer services and schemas for structured candidate/job signals."""

from pydantic import BaseModel, Field


class JobRequirements(BaseModel):
    """Structured requirements extracted from a job description."""

    hard_skills: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    years_experience_min: int | None = None
    education_requirements: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


class CandidateSignals(BaseModel):
    """Structured candidate signals extracted from resume content."""

    skills: list[str] = Field(default_factory=list)
    experience_highlights: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    summary: str | None = None


class ExtractionDiagnostics(BaseModel):
    """Operational metadata and diagnostics for extraction calls."""

    model_alias: str
    attempts: int = 0
    fallback_used: bool = False
    latency_ms: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None
