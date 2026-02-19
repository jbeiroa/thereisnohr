from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.storage import models


@dataclass
class CandidateRepository:
    session: Session

    def create(
        self,
        name: str | None,
        email: str | None = None,
        external_id: str | None = None,
    ) -> models.Candidate:
        candidate = models.Candidate(name=name, email=email, external_id=external_id)
        self.session.add(candidate)
        self.session.flush()
        return candidate

    def get_by_external_id(self, external_id: str) -> models.Candidate | None:
        return self.session.scalar(
            select(models.Candidate).where(models.Candidate.external_id == external_id)
        )

    def get_or_create_by_external_id(
        self,
        *,
        external_id: str,
        name: str | None = None,
        email: str | None = None,
    ) -> tuple[models.Candidate, bool]:
        existing = self.get_by_external_id(external_id)
        if existing is not None:
            return existing, False
        return self.create(name=name, email=email, external_id=external_id), True

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

    def get_by_source_file(self, source_file: str) -> models.Resume | None:
        return self.session.scalar(select(models.Resume).where(models.Resume.source_file == source_file))

    def create(
        self,
        candidate_id: int,
        source_file: str,
        raw_text: str,
        *,
        parsed_json: dict | None = None,
        language: str | None = None,
    ) -> models.Resume:
        resume = models.Resume(
            candidate_id=candidate_id,
            source_file=source_file,
            raw_text=raw_text,
            parsed_json=parsed_json,
            language=language,
        )
        self.session.add(resume)
        self.session.flush()
        return resume


@dataclass
class ResumeSectionRepository:
    session: Session

    def create(
        self,
        *,
        resume_id: int,
        section_type: str,
        content: str,
        metadata_json: dict | None = None,
        tokens: int | None = None,
    ) -> models.ResumeSection:
        section = models.ResumeSection(
            resume_id=resume_id,
            section_type=section_type,
            content=content,
            metadata_json=metadata_json,
            tokens=tokens,
        )
        self.session.add(section)
        self.session.flush()
        return section
