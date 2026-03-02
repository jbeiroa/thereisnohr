"""Persistence utilities, ORM models, and repository implementations."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from src.core.config import get_settings

Base = declarative_base()


def make_engine(echo: bool = False):
    """Runs make engine logic.

    Args:
        echo (bool): When true enables SQL echo logging on the engine.
    """
    settings = get_settings()
    return create_engine(settings.database_url, echo=echo)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=make_engine())


def get_session() -> Session:
    """Fetches a record or value needed by downstream workflow steps.

    Returns:
        Session: Return value for this function.
    """
    return SessionLocal()
