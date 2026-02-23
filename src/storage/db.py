"""Application module `src.storage.db`."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from src.core.config import get_settings

Base = declarative_base()


def make_engine(echo: bool = False):
    """Run make engine.

    Args:
        echo: Input parameter.

    Returns:
        object: Computed result.

    """
    settings = get_settings()
    return create_engine(settings.database_url, echo=echo)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=make_engine())


def get_session() -> Session:
    """Get session.

    Returns:
        object: Computed result.

    """
    return SessionLocal()
