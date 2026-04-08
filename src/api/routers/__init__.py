"""API Routers module."""

from src.api.routers.candidates import router as candidates_router
from src.api.routers.ingest import router as ingest_router
from src.api.routers.jobs import router as jobs_router
from src.api.routers.matches import router as matches_router
from src.api.routers.tasks import router as tasks_router

__all__ = [
    "candidates_router",
    "ingest_router",
    "jobs_router",
    "matches_router",
    "tasks_router",
]
