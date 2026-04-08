"""Candidates-related API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.schemas import CandidateResponse
from src.storage import models
from src.storage.db import get_session

router = APIRouter(prefix="/candidates", tags=["Candidates"])


def get_db():
    with get_session() as session:
        yield session


@router.get("/", response_model=list[CandidateResponse])
def list_candidates(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List candidates."""
    candidates = db.scalars(select(models.Candidate).offset(skip).limit(limit)).all()
    return candidates


@router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate(candidate_id: int, db: Session = Depends(get_db)):
    """Get candidate details."""
    candidate = db.get(models.Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate
