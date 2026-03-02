"""FastAPI application and route definitions."""

from fastapi import FastAPI

from src.core.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name)


@app.get("/health")
def health() -> dict[str, str]:
    """Runs health logic.

    Returns:
        dict[str, str]: Return value for this function.
    """
    return {"status": "ok"}
