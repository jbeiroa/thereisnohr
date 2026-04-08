"""FastAPI application and route definitions."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import (
    candidates_router,
    ingest_router,
    jobs_router,
    matches_router,
    tasks_router,
)
from src.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)

# Enable CORS for local UI development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(jobs_router, prefix="/api")
app.include_router(matches_router, prefix="/api")
app.include_router(candidates_router, prefix="/api")
app.include_router(ingest_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str]:
    """Runs health logic.

    Returns:
        dict[str, str]: Return value for this function.
    """
    return {"status": "ok"}
