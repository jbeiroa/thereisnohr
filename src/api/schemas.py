"""Pydantic schemas for the API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TaskResponse(BaseModel):
    """Schema for returning task information."""

    id: int
    task_type: str
    status: str
    input_payload: dict | None = None
    output_payload: dict | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobCreateRequest(BaseModel):
    """Schema for creating a new job posting."""

    title: str
    description: str


class JobResponse(BaseModel):
    """Schema for returning job information."""

    id: int
    title: str
    description: str
    requirements_json: dict | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CandidateResponse(BaseModel):
    """Schema for returning candidate information."""

    id: int
    external_id: str | None = None
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    links: list[str] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MatchResponse(BaseModel):
    """Schema for returning match information."""

    id: int
    job_id: int
    candidate_id: int
    retrieval_score: float | None = None
    rerank_score: float | None = None
    final_score: float | None = None
    reasons_json: dict | None = None
    interview_pack_json: dict | None = None
    created_at: datetime

    candidate: CandidateResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class RankRequest(BaseModel):
    """Schema for ranking candidates for a job."""

    top_k: int = 5


class IngestResumesRequest(BaseModel):
    """Schema for triggering batch ingestion."""

    input_dir: str = "data"
    pattern: str = "*.pdf"
