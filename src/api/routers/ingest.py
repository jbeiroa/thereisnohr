"""Ingestion-related API endpoints."""

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.schemas import IngestResumesRequest, TaskResponse
from src.api.tasks import execute_task
from src.ingest.service import IngestionService
from src.storage import models
from src.storage.db import get_session
from src.storage.repositories import TaskRepository

router = APIRouter(prefix="/ingest", tags=["Ingestion"])


def get_db():
    with get_session() as session:
        yield session


def run_ingest_resumes(input_dir: str, pattern: str, cleanup: bool = False) -> dict:
    input_dir_path = Path(input_dir)
    if not input_dir_path.is_absolute():
        input_dir_path = (Path.cwd() / input_dir_path).resolve()

    service = IngestionService()
    files = service.discover_pdf_files(input_dir_path, pattern)

    results = []

    for file_path in files:
        with get_session() as session:
            try:
                result = service.ingest_pdf(file_path, session)
                session.commit()
                results.append(
                    {
                        "source_file": str(file_path),
                        "status": result.status,
                        "candidate_id": result.candidate_id,
                        "resume_id": result.resume_id,
                    }
                )
            except Exception as e:
                session.rollback()
                results.append({"source_file": str(file_path), "status": "error", "error": str(e)})

    if cleanup and input_dir_path.exists():
        shutil.rmtree(input_dir_path)

    return {"processed": len(files), "results": results}


@router.post("/resumes", response_model=TaskResponse)
def ingest_resumes(
    request: IngestResumesRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    """Trigger batch resume processing."""
    repo = TaskRepository(db)

    task_type = "ingest_resumes"
    input_payload = request.model_dump()

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
        execute_task, task.id, run_ingest_resumes, request.input_dir, request.pattern
    )
    return task


@router.post("/upload", response_model=TaskResponse)
def upload_resumes(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Handles multiple file uploads and processes them asynchronously."""
    # Create temporary directory for these files
    temp_dir = tempfile.mkdtemp(prefix="ats_upload_")
    temp_path = Path(temp_dir)

    for file in files:
        if not file.filename:
            continue
        file_dest = temp_path / file.filename
        with open(file_dest, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

    repo = TaskRepository(db)
    task_type = "upload_resumes"
    input_payload = {"processed_count": len(files), "temp_dir": temp_dir}

    task = repo.create_task(task_type=task_type, input_payload=input_payload)
    db.commit()
    db.refresh(task)

    # Reusing run_ingest_resumes with cleanup=True to remove the temp folder after processing
    background_tasks.add_task(execute_task, task.id, run_ingest_resumes, temp_dir, "*.pdf", True)
    return task
