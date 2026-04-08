"""Tasks-related API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.schemas import TaskResponse
from src.storage import models
from src.storage.db import get_session

router = APIRouter(prefix="/tasks", tags=["Tasks"])


def get_db():
    with get_session() as session:
        yield session


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
    """Get task details."""
    task = db.get(models.AsyncTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
