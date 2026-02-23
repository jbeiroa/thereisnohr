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
        phone: str | None = None,
        external_id: str | None = None,
    ) -> models.Candidate:
        candidate = models.Candidate(name=name, email=email, phone=phone, external_id=external_id)
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
        phone: str | None = None,
    ) -> tuple[models.Candidate, bool]:
        existing = self.get_by_external_id(external_id)
        if existing is not None:
            self._merge_identity_fields(existing, name=name, email=email, phone=phone)
            return existing, False
        return self.create(name=name, email=email, phone=phone, external_id=external_id), True

    def get_or_create_by_identity_key(
        self,
        *,
        identity_key: str,
        name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> tuple[models.Candidate, bool]:
        return self.get_or_create_by_external_id(
            external_id=identity_key,
            name=name,
            email=email,
            phone=phone,
        )

    def list_all(self) -> list[models.Candidate]:
        return list(self.session.scalars(select(models.Candidate)).all())

    def _merge_identity_fields(
        self,
        candidate: models.Candidate,
        *,
        name: str | None,
        email: str | None,
        phone: str | None,
    ) -> None:
        if name and not candidate.name:
            candidate.name = name
        if email and not candidate.email:
            candidate.email = email
        if phone and not candidate.phone:
            candidate.phone = phone
        self.session.flush()


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

    def get_by_content_hash(self, content_hash: str) -> models.Resume | None:
        return self.session.scalar(select(models.Resume).where(models.Resume.content_hash == content_hash))

    def create(
        self,
        candidate_id: int,
        source_file: str,
        content_hash: str | None,
        raw_text: str,
        *,
        parsed_json: dict | None = None,
        language: str | None = None,
    ) -> models.Resume:
        resume = models.Resume(
            candidate_id=candidate_id,
            source_file=source_file,
            content_hash=content_hash,
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
