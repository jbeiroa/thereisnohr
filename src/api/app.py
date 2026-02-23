"""Application module `src.api.app`."""

from fastapi import FastAPI

from src.core.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name)


@app.get("/health")
def health() -> dict[str, str]:
    """Run health.

    Returns:
        object: Computed result.

    """
    return {"status": "ok"}
