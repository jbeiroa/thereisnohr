from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.storage import models


@dataclass
class CandidateRepository:
    session: Session

    def create(self, name: str | None, email: str | None = None) -> models.Candidate:
        candidate = models.Candidate(name=name, email=email)
        self.session.add(candidate)
        self.session.flush()
        return candidate

    def list_all(self) -> list[models.Candidate]:
        return list(self.session.scalars(select(models.Candidate)).all())


@dataclass
class JobPostingRepository:
    session: Session

    def create(self, title: str, description: str) -> models.JobPosting:
        job = models.JobPosting(title=title, description=description)
        self.session.add(job)
        self.session.flush()
        return job


@dataclass
class ResumeRepository:
    session: Session

    def create(self, candidate_id: int, source_file: str, raw_text: str) -> models.Resume:
        resume = models.Resume(
            candidate_id=candidate_id,
            source_file=source_file,
            raw_text=raw_text,
        )
        self.session.add(resume)
        self.session.flush()
        return resume
