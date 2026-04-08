"""Matches-related API endpoints."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.api.schemas import MatchResponse, TaskResponse
from src.api.tasks import execute_task
from src.extract.types import CandidateSignals, JobRequirements
from src.ranking.service import RankingService
from src.ranking.types import RankExplanation, RankInput
from src.storage import models
from src.storage.db import get_session
from src.storage.repositories import ResumeRepository, TaskRepository

router = APIRouter(prefix="/matches", tags=["Matches"])


def get_db():
    with get_session() as session:
        yield session


def run_generate_prep(match_id: int) -> dict:
    with get_session() as session:
        match = session.get(models.Match, match_id)
        if not match:
            raise ValueError(f"Match {match_id} not found")

        job = session.get(models.JobPosting, match.job_id)
        if not job:
            raise ValueError(f"Job {match.job_id} not found")
        requirements = JobRequirements.model_validate(job.requirements_json)

        resume_repo = ResumeRepository(session)
        latest_resume = resume_repo.get_latest_resume_by_candidate_id(match.candidate_id)
        if not latest_resume or not latest_resume.signals_json:
            raise ValueError("Missing candidate signals.")
        signals = CandidateSignals.model_validate(latest_resume.signals_json)

        rank_input = RankInput(
            candidate_id=match.candidate_id,
            retrieval_score=match.retrieval_score or 0.0,
            requirements=requirements,
            signals=signals,
        )

        explanation = None
        if (
            match.reasons_json
            and "explanation" in match.reasons_json
            and match.reasons_json["explanation"]
        ):
            explanation = RankExplanation.model_validate(match.reasons_json["explanation"])

        if not explanation:
            raise ValueError("No ranking explanation found to base the prep pack on.")

        ranking_service = RankingService()
        pack = ranking_service.generate_interview_pack(rank_input, explanation)
        if pack:
            match.interview_pack_json = pack.model_dump()
            session.commit()
            return pack.model_dump()
        else:
            raise ValueError("Failed to generate interview pack.")


@router.get("/", response_model=list[MatchResponse])
def list_matches(
    job_id: int | None = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """List matches."""
    query = select(models.Match).options(joinedload(models.Match.candidate))
    if job_id:
        query = query.where(models.Match.job_id == job_id)
    matches = db.scalars(
        query.order_by(models.Match.final_score.desc().nullslast()).offset(skip).limit(limit)
    ).all()
    return matches


@router.get("/{match_id}", response_model=MatchResponse)
def get_match(match_id: int, db: Session = Depends(get_db)):
    """Get match details."""
    match = db.scalar(
        select(models.Match)
        .options(joinedload(models.Match.candidate))
        .where(models.Match.id == match_id)
    )
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return match


@router.post("/{match_id}/prep", response_model=TaskResponse)
def generate_prep(match_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Generate an interview prep pack for a match."""
    repo = TaskRepository(db)

    match = db.get(models.Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    task_type = "generate_prep"
    input_payload = {"match_id": match_id}

    existing = db.scalar(
        select(models.AsyncTask)
        .where(models.AsyncTask.task_type == task_type)
        .where(models.AsyncTask.input_payload == input_payload)
        .where(models.AsyncTask.status.in_(["PENDING", "RUNNING"]))
    )
    if existing:
        return existing

    task = repo.create_task(task_type=task_type, input_payload=input_payload)
    db.commit()
    db.refresh(task)
    background_tasks.add_task(execute_task, task.id, run_generate_prep, match_id)
    return task
