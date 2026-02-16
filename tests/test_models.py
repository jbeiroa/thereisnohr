from src.storage.db import Base
from src.storage import models  # noqa: F401


def test_stage1_tables_registered() -> None:
    expected_tables = {
        "candidates",
        "resumes",
        "resume_sections",
        "job_postings",
        "embeddings",
        "matches",
    }
    assert expected_tables.issubset(set(Base.metadata.tables.keys()))
