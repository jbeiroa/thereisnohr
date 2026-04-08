"""Job-related API endpoints."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.schemas import JobCreateRequest, JobResponse, RankRequest, TaskResponse
from src.api.tasks import execute_task
from src.ingest.service import IngestionService
from src.ranking.workflow import RankingWorkflow
from src.storage import models
from src.storage.db import get_session
from src.storage.repositories import TaskRepository

router = APIRouter(prefix="/jobs", tags=["Jobs"])


def get_db():
    with get_session() as session:
        yield session


def run_ingest_job(title: str, description: str) -> int:
    with get_session() as session:
        service = IngestionService()
        job_id = service.ingest_job(title=title, description=description, session=session)
        session.commit()
        return job_id


def run_rank_job(job_id: int, top_k: int) -> list[int]:
    with get_session() as session:
        workflow = RankingWorkflow(session)
        ranked = workflow.run(job_id=job_id, top_k=top_k)
        session.commit()
        return [r.candidate_id for r in ranked]


@router.get("/", response_model=list[JobResponse])
def list_jobs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all jobs."""
    jobs = db.scalars(select(models.JobPosting).offset(skip).limit(limit)).all()
    return jobs


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    """Get job details."""
    job = db.get(models.JobPosting, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/", response_model=TaskResponse)
def create_job(
    request: JobCreateRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    """Submit a new job posting for async extraction."""
    repo = TaskRepository(db)

    task_type = "ingest_job"
    input_payload = request.model_dump()

    # Check idempotency
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
    background_tasks.add_task(
        execute_task, task.id, run_ingest_job, request.title, request.description
    )
    return task


@router.post("/{job_id}/rank", response_model=TaskResponse)
def rank_job(
    job_id: int,
    request: RankRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Trigger ranking for a job."""
    repo = TaskRepository(db)

    # Ensure job exists
    job = db.get(models.JobPosting, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    task_type = "rank_job"
    input_payload = {"job_id": job_id, "top_k": request.top_k}

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
    background_tasks.add_task(execute_task, task.id, run_rank_job, job_id, request.top_k)
    return task
