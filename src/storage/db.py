from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from src.core.config import get_settings

Base = declarative_base()


def make_engine(echo: bool = False):
    settings = get_settings()
    return create_engine(settings.database_url, echo=echo)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=make_engine())


def get_session() -> Session:
    return SessionLocal()
