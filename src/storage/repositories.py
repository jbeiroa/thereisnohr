"""Repository classes for creating and querying ATS persistence models."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.storage import models


@dataclass
class CandidateRepository:
    """Repository for querying and persisting candidate rows."""

    session: Session

    def create(
        self,
        name: str | None,
        email: str | None = None,
        phone: str | None = None,
        external_id: str | None = None,
        links: list[str] | None = None,
    ) -> models.Candidate:
        """Creates and flushes a new persistence model row.

        Args:
            name (str | None): Candidate name value to persist or score.
            email (str | None): Candidate email used for identity and deduplication.
            phone (str | None): Candidate phone number used for identity and deduplication.
            external_id (str | None): Stable external identity key for candidate upserts.
            links (list[str] | None): Profile URLs associated with the candidate record.

        Returns:
            models.Candidate: Persisted ORM instance returned after flush.
        """
        candidate = models.Candidate(name=name, email=email, phone=phone, external_id=external_id, links=links)
        self.session.add(candidate)
        self.session.flush()
        return candidate

    def get_by_external_id(self, external_id: str) -> models.Candidate | None:
        """Looks up a candidate using its external identity key.

        Args:
            external_id (str): Stable external identity key for candidate upserts.

        Returns:
            models.Candidate | None: Matching candidate row, or ``None``.
        """
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
        links: list[str] | None = None,
        name_confidence: float | None = None,
    ) -> tuple[models.Candidate, bool]:
        """Returns an existing record when present, otherwise creates and returns a new one.

        Args:
            external_id (str): Stable external identity key for candidate upserts.
            name (str | None): Candidate name value to persist or score.
            email (str | None): Candidate email used for identity and deduplication.
            phone (str | None): Candidate phone number used for identity and deduplication.
            links (list[str] | None): Profile URLs associated with the candidate record.
            name_confidence (float | None): Confidence score for the extracted candidate name.

        Returns:
            tuple[models.Candidate, bool]: Persisted ORM instance returned after flush.
        """
        existing = self.get_by_external_id(external_id)
        if existing is not None:
            self._merge_identity_fields(
                existing,
                name=name,
                email=email,
                phone=phone,
                links=links,
                name_confidence=name_confidence,
            )
            return existing, False
        return self.create(name=name, email=email, phone=phone, external_id=external_id, links=links), True

    def get_or_create_by_identity_key(
        self,
        *,
        identity_key: str,
        name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        links: list[str] | None = None,
        name_confidence: float | None = None,
    ) -> tuple[models.Candidate, bool]:
        """Returns an existing record when present, otherwise creates and returns a new one.

        Args:
            identity_key (str): Derived identity key used for candidate deduplication.
            name (str | None): Candidate name value to persist or score.
            email (str | None): Candidate email used for identity and deduplication.
            phone (str | None): Candidate phone number used for identity and deduplication.
            links (list[str] | None): Profile URLs associated with the candidate record.
            name_confidence (float | None): Confidence score for the extracted candidate name.

        Returns:
            tuple[models.Candidate, bool]: Persisted ORM instance returned after flush.
        """
        return self.get_or_create_by_external_id(
            external_id=identity_key,
            name=name,
            email=email,
            phone=phone,
            links=links,
            name_confidence=name_confidence,
        )

    def list_all(self) -> list[models.Candidate]:
        """Returns all records matching the query criteria.

        Returns:
            list[models.Candidate]: Persisted ORM instance returned after flush.
        """
        return list(self.session.scalars(select(models.Candidate)).all())

    def _merge_identity_fields(
        self,
        candidate: models.Candidate,
        *,
        name: str | None,
        email: str | None,
        phone: str | None,
        links: list[str] | None,
        name_confidence: float | None,
    ) -> None:
        """Merges newer identity signals into an existing candidate row.

        Args:
            candidate (models.Candidate): Candidate ORM instance currently being evaluated.
            name (str | None): Candidate name value to persist or score.
            email (str | None): Candidate email used for identity and deduplication.
            phone (str | None): Candidate phone number used for identity and deduplication.
            links (list[str] | None): Profile URLs associated with the candidate record.
            name_confidence (float | None): Confidence score for the extracted candidate name.
        """
        existing_quality = _estimate_name_quality(candidate.name)
        incoming_quality = max(float(name_confidence or 0.0), _estimate_name_quality(name))
        if name and (
            not candidate.name
            or (incoming_quality >= 0.70 and existing_quality < 0.70)
        ):
            candidate.name = name
        if email and not candidate.email:
            candidate.email = email
        if phone and not candidate.phone:
            candidate.phone = phone
        if links:
            merged = sorted(set(_normalize_links(candidate.links) + _normalize_links(links)))
            candidate.links = merged
        self.session.flush()


def _normalize_links(value: list[str] | dict | None) -> list[str]:
    """Normalizes mixed link payloads into a plain list of URL strings.

    Args:
        value (list[str] | dict | None): Scalar/list input normalized or rendered by this helper.

    Returns:
        list[str]: Non-empty URL strings extracted from the input payload.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    if isinstance(value, dict):
        urls = value.get("urls")
        if isinstance(urls, list):
            return [str(v) for v in urls if str(v).strip()]
    return []


def _estimate_name_quality(name: str | None) -> float:
    """Lazily imports name-quality heuristic to avoid repository import cycles."""
    from src.ingest.identity import estimate_name_quality

    return estimate_name_quality(name)


@dataclass
class JobPostingRepository:
    """Repository for querying and persisting job posting rows."""

    session: Session

    def create(self, title: str, description: str) -> models.JobPosting:
        """Creates and flushes a new persistence model row.

        Args:
            title (str): Human-readable job title.
            description (str): Full job-description text for scoring/retrieval.

        Returns:
            models.JobPosting: Persisted ORM instance returned after flush.
        """
        job = models.JobPosting(title=title, description=description)
        self.session.add(job)
        self.session.flush()
        return job


@dataclass
class ResumeRepository:
    """Repository for querying and persisting resume rows."""

    session: Session

    def get_by_source_file(self, source_file: str) -> models.Resume | None:
        """Finds a resume row by its stored source-file path.

        Args:
            source_file (str): Source file path string stored for idempotency checks.

        Returns:
            models.Resume | None: Persisted ORM instance returned after flush.
        """
        return self.session.scalar(select(models.Resume).where(models.Resume.source_file == source_file))

    def get_by_content_hash(self, content_hash: str) -> models.Resume | None:
        """Finds a resume row by content hash for idempotency checks.

        Args:
            content_hash (str): Deterministic hash used to detect duplicate resume content.

        Returns:
            models.Resume | None: Persisted ORM instance returned after flush.
        """
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
        """Creates and flushes a new persistence model row.

        Args:
            candidate_id (int): Input value used by `candidate_id`.
            source_file (str): Source file path string stored for idempotency checks.
            content_hash (str | None): Deterministic hash used to detect duplicate resume content.
            raw_text (str): Raw resume text/markdown to persist.
            parsed_json (dict | None): Parser artifact payload persisted in the resume row.
            language (str | None): Detected document language code.

        Returns:
            models.Resume: Persisted ORM instance returned after flush.
        """
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
    """Repository for querying and persisting resume section rows."""

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
        """Creates and flushes a new persistence model row.

        Args:
            resume_id (int): Resume primary key used to link section rows.
            section_type (str): Canonical section label to store or evaluate.
            content (str): Section body content associated with the heading.
            metadata_json (dict | None): Input value used by `metadata_json`.
            tokens (int | None): Input value used by `tokens`.

        Returns:
            models.ResumeSection: Persisted ORM instance returned after flush.
        """
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


@dataclass
class EmbeddingRepository:
    """Repository for querying and persisting embedding rows."""

    session: Session

    def create(
        self,
        *,
        owner_type: str,
        owner_id: int,
        model: str,
        vector: list[float],
        text_hash: str,
    ) -> models.Embedding:
        """Creates and flushes one embedding row.

        Args:
            owner_type (str): Entity type owning this embedding.
            owner_id (int): Entity identifier owning this embedding.
            model (str): Provider/model identifier used to generate the vector.
            vector (list[float]): Embedding vector payload.
            text_hash (str): Deterministic content hash for the embedded text.

        Returns:
            models.Embedding: Persisted ORM instance returned after flush.
        """
        dimensions = len(vector)
        if dimensions <= 0:
            raise ValueError("Embedding vector must contain at least one dimension")

        registered = self.session.scalar(
            select(models.EmbeddingModel).where(models.EmbeddingModel.model == model)
        )
        if registered is None:
            self.session.add(models.EmbeddingModel(model=model, dimensions=dimensions))
            self.session.flush()
        elif int(registered.dimensions) != dimensions:
            raise ValueError(
                f"Embedding model '{model}' expects {registered.dimensions} dimensions, got {dimensions}"
            )

        embedding = models.Embedding(
            owner_type=owner_type,
            owner_id=owner_id,
            model=model,
            dimensions=dimensions,
            vector=vector,
            text_hash=text_hash,
        )
        self.session.add(embedding)
        self.session.flush()
        return embedding
