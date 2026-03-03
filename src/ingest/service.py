"""Coordinates parsing, identity resolution, and persistence for PDF resume ingestion."""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.ingest.entities import ParsedResume
from src.ingest.identity import ModelNameResolver, compute_content_hash, extract_identity
from src.ingest.model_fallback import LLMFallbackResolver
from src.ingest.parser import PDFResumeParser
from src.llm.client import LLMClient
from src.llm.factory import build_default_llm_client
from src.storage.repositories import (
    CandidateRepository,
    EmbeddingRepository,
    ResumeRepository,
    ResumeSectionRepository,
)


@dataclass(frozen=True)
class IngestionResult:
    """Outcome summary returned after processing one source resume."""

    status: str
    source_file: str
    candidate_id: int | None = None
    resume_id: int | None = None
    section_count: int = 0
    identity_confidence: float | None = None
    avg_section_confidence: float | None = None


@dataclass
class IngestionService:
    """Coordinates parsing, identity resolution, and persistence for resumes."""

    parser: PDFResumeParser | None = None
    llm_client: LLMClient | None = None
    enable_name_model_fallback: bool | None = None
    enable_section_model_fallback: bool | None = None
    name_rule_trigger_threshold: float | None = None
    name_model_accept_threshold: float | None = None
    section_model_accept_threshold: float | None = None
    section_model_max_chars: int | None = None

    def __post_init__(self) -> None:
        """Initializes default runtime dependencies and configuration values after dataclass construction.
        """
        settings = get_settings()
        if self.parser is None:
            self.parser = PDFResumeParser()
        if self.enable_name_model_fallback is None:
            self.enable_name_model_fallback = settings.ingest_enable_name_model_fallback
        if self.enable_section_model_fallback is None:
            self.enable_section_model_fallback = settings.ingest_enable_section_model_fallback
        if self.name_rule_trigger_threshold is None:
            self.name_rule_trigger_threshold = settings.ingest_name_rule_trigger_threshold
        if self.name_model_accept_threshold is None:
            self.name_model_accept_threshold = settings.ingest_name_model_accept_threshold
        if self.section_model_accept_threshold is None:
            self.section_model_accept_threshold = settings.ingest_section_model_accept_threshold
        if self.section_model_max_chars is None:
            self.section_model_max_chars = settings.ingest_section_model_max_chars

    def discover_pdf_files(self, input_dir: Path, pattern: str = "*.pdf") -> list[Path]:
        """Recursively discovers PDF files that should enter ingestion.

        Args:
            input_dir (Path): Root directory scanned for candidate PDF files.
            pattern (str): File glob used during recursive discovery.

        Returns:
            list[Path]: Sorted list of files that match the supplied pattern.

        Raises:
            FileNotFoundError: Raised when validation or execution constraints are violated.
        """
        if not input_dir.exists():
            raise FileNotFoundError(f"Input directory does not exist: {input_dir}")
        return sorted(path for path in input_dir.rglob(pattern) if path.is_file())

    def parse_pdf(self, path: Path) -> ParsedResume:
        """Parses one PDF file into the normalized ``ParsedResume`` contract.

        Args:
            path (Path): Filesystem path of the file being parsed or ingested.

        Returns:
            ParsedResume: Parsed text, sections, language, and link artifacts.
        """
        assert self.parser is not None
        return self.parser.parse(path)

    def ingest_pdf(self, path: Path, session: Session) -> IngestionResult:
        """Ingests one resume file into candidate/resume/section tables.

        Args:
            path (Path): Filesystem path of the file being parsed or ingested.
            session (Session): Database session used for repository operations in this call.

        Returns:
            IngestionResult: Final status with key IDs and confidence metrics.
        """
        parsed = self.parse_pdf(path)
        resume_content_hash = compute_content_hash(parsed.clean_text)

        candidate_repo = CandidateRepository(session)
        resume_repo = ResumeRepository(session)
        section_repo = ResumeSectionRepository(session)
        embedding_repo = EmbeddingRepository(session)

        existing = resume_repo.get_by_source_file(parsed.source_file)
        if existing is not None:
            return IngestionResult(
                status="skipped_existing_resume",
                source_file=parsed.source_file,
                candidate_id=existing.candidate_id,
                resume_id=existing.id,
                section_count=0,
            )

        existing_content = resume_repo.get_by_content_hash(resume_content_hash)
        if existing_content is not None:
            return IngestionResult(
                status="skipped_existing_content",
                source_file=parsed.source_file,
                candidate_id=existing_content.candidate_id,
                resume_id=existing_content.id,
                section_count=0,
            )

        fallback_resolver = self._build_llm_fallback_resolver() if self.enable_name_model_fallback else None
        identity = extract_identity(
            parsed,
            model_name_resolver=ModelNameResolver(llm_resolver=fallback_resolver),
            allow_model_fallback=bool(self.enable_name_model_fallback),
            name_fallback_trigger_threshold=float(self.name_rule_trigger_threshold or 0.60),
            name_model_accept_threshold=float(self.name_model_accept_threshold or 0.70),
        )
        name_confidence = float((identity.signals.get("confidence_inputs") or {}).get("name_confidence", 0.0))
        candidate, _ = candidate_repo.get_or_create_by_identity_key(
            identity_key=identity.identity_key,
            name=identity.name,
            email=identity.email,
            phone=identity.phone,
            links=parsed.links,
            name_confidence=name_confidence,
        )

        section_payloads = self._build_section_payloads(parsed=parsed, resume_id=0)
        effective_section_names = list(dict.fromkeys(payload["section_type"] for payload in section_payloads))

        resume = resume_repo.create(
            candidate_id=candidate.id,
            source_file=parsed.source_file,
            content_hash=resume_content_hash,
            raw_text=parsed.raw_text,
            parsed_json={
                "clean_text": parsed.clean_text,
                "links": parsed.links,
                "parser_version": parsed.parser_version,
                "section_names": effective_section_names,
                "identity": {
                    "identity_key": identity.identity_key,
                    "name": identity.name,
                    "email": identity.email,
                    "phone": identity.phone,
                    "confidence": identity.confidence,
                    "signals": identity.signals,
                },
            },
            language=parsed.language,
        )

        section_count = 0
        section_confidences: list[float] = []
        created_sections = []
        for payload in section_payloads:
            section = section_repo.create(
                resume_id=resume.id,
                section_type=payload["section_type"],
                content=payload["content"],
                metadata_json=payload["metadata_json"],
                tokens=len(payload["content"].split()),
            )
            created_sections.append(section)
            section_count += 1
            section_confidences.append(payload["metadata_json"]["section_confidence"])

        embedding_meta = self._persist_section_embeddings(
            resume_sections=created_sections,
            embedding_repo=embedding_repo,
        )
        resume_parsed_json = dict(getattr(resume, "parsed_json", None) or {})
        resume_parsed_json["embedding"] = embedding_meta
        if hasattr(resume, "parsed_json"):
            resume.parsed_json = resume_parsed_json

        avg_section_confidence = (
            round(sum(section_confidences) / len(section_confidences), 4)
            if section_confidences
            else None
        )

        return IngestionResult(
            status="ingested",
            source_file=parsed.source_file,
            candidate_id=candidate.id,
            resume_id=resume.id,
            section_count=section_count,
            identity_confidence=identity.confidence,
            avg_section_confidence=avg_section_confidence,
        )

    def _build_section_payloads(self, *, parsed: ParsedResume, resume_id: int) -> list[dict]:
        """Builds normalized section payloads ready for database persistence.

        Args:
            parsed (ParsedResume): Parsed resume payload returned by `PDFResumeParser`.
            resume_id (int): Resume primary key used to link section rows.

        Returns:
            list[dict]: Section dictionaries consumed by ``ResumeSectionRepository``.
        """
        payloads: list[dict] = []
        fallback_resolver = self._build_llm_fallback_resolver() if self.enable_section_model_fallback else None

        for item in parsed.section_items:
            signals = item.signals or {}
            recat = signals.get("recategorization_candidate")
            base_type = item.normalized_type
            final_type = base_type
            model_section_type: str | None = None
            model_section_confidence: float | None = None
            routed = False
            if self._should_route_section(item.normalized_type, item.confidence) and fallback_resolver is not None:
                routed = True
                excerpt = item.content[: int(self.section_model_max_chars or 700)]
                try:
                    prediction = fallback_resolver.classify_section(
                        raw_heading=item.raw_heading,
                        content_excerpt=excerpt,
                        language=parsed.language,
                    )
                    model_section_type = prediction.section_type
                    model_section_confidence = float(prediction.confidence)
                    if (
                        model_section_confidence >= float(self.section_model_accept_threshold or 0.75)
                        and model_section_type != base_type
                    ):
                        final_type = model_section_type
                except Exception:
                    model_section_type = None
                    model_section_confidence = None

            payloads.append(
                {
                    "resume_id": resume_id,
                    "section_type": final_type,
                    "content": item.content,
                    "metadata_json": {
                        "parser_version": parsed.parser_version,
                        "section_confidence": item.confidence,
                        "diagnostic_flags": signals.get("diagnostic_flags", []),
                        "confidence_inputs": signals.get("confidence_inputs", {}),
                        "recategorization_candidate": recat,
                        "original_section_type": base_type,
                        "model_section_type": model_section_type,
                        "model_section_confidence": model_section_confidence,
                        "section_routed_by_model": routed,
                    },
                }
            )
        return payloads

    def _should_route_section(self, section_type: str, confidence: float) -> bool:
        """Helper that handles should route section.

        Args:
            section_type (str): Canonical section label to store or evaluate.
            confidence (float): Confidence score used to decide rerouting or acceptance.

        Returns:
            bool: True when the condition is satisfied; otherwise False.
        """
        return section_type == "general" or confidence < float(self.section_model_accept_threshold or 0.75)

    def _build_llm_fallback_resolver(self) -> LLMFallbackResolver | None:
        """Helper that handles build llm fallback resolver.

        Returns:
            LLMFallbackResolver | None: Return value for this function.
        """
        client = self.llm_client
        if client is None:
            try:
                client = build_default_llm_client()
            except Exception:
                return None
        return LLMFallbackResolver(client)

    def _resolve_llm_client(self) -> LLMClient | None:
        """Returns an LLM client instance if one is available."""
        if self.llm_client is not None:
            return self.llm_client
        try:
            return build_default_llm_client()
        except Exception:
            return None

    def _persist_section_embeddings(
        self,
        *,
        resume_sections: list,
        embedding_repo: EmbeddingRepository,
    ) -> dict:
        """Embeds non-skill sections and persists vectors per section."""
        settings = get_settings()
        candidates: list[tuple[int, str]] = []
        for section in resume_sections:
            section_type = str(getattr(section, "section_type", "") or "")
            content = str(getattr(section, "content", "") or "")
            if section_type == "skills" or not content.strip():
                continue
            section_id = getattr(section, "id", None)
            if not isinstance(section_id, int):
                continue
            candidates.append((section_id, content))

        if not candidates:
            return {
                "status": "skipped",
                "model_alias": settings.embedding_model_alias,
                "vector_count": 0,
            }

        client = self._resolve_llm_client()
        if client is None:
            return {
                "status": "error",
                "model_alias": settings.embedding_model_alias,
                "vector_count": 0,
                "error_type": "client_unavailable",
            }

        texts = [content for _, content in candidates]
        try:
            vectors, metadata = client.embed_with_meta(
                texts=texts,
                embedding_model_alias=settings.embedding_model_alias,
            )
        except Exception as exc:
            return {
                "status": "error",
                "model_alias": settings.embedding_model_alias,
                "vector_count": 0,
                "error_type": type(exc).__name__,
            }
        if len(vectors) != len(candidates):
            return {
                "status": "error",
                "model_alias": settings.embedding_model_alias,
                "vector_count": 0,
                "error_type": "vector_count_mismatch",
            }

        persisted = 0
        selected_model = metadata.selected_model or settings.embedding_model_alias
        try:
            for (section_id, content), vector in zip(candidates, vectors):
                embedding_repo.create(
                    owner_type="resume_section",
                    owner_id=section_id,
                    model=selected_model,
                    vector=vector,
                    text_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                )
                persisted += 1
        except Exception as exc:
            return {
                "status": "error",
                "model_alias": settings.embedding_model_alias,
                "vector_count": 0,
                "error_type": type(exc).__name__,
            }

        return {
            "status": "ok",
            "model_alias": settings.embedding_model_alias,
            "selected_model": selected_model,
            "vector_count": persisted,
            "estimated_cost_usd": metadata.usage.estimated_cost_usd,
        }

    def _build_candidate_external_id(self, path: Path) -> str:
        """Helper that handles build candidate external id.

        Args:
            path (Path): Filesystem path of the file being parsed or ingested.

        Returns:
            str: Normalized string result.
        """
        digest = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:16]
        return f"resume_file:{digest}"

    def _infer_candidate_name(self, path: Path) -> str:
        """Helper that handles infer candidate name.

        Args:
            path (Path): Filesystem path of the file being parsed or ingested.

        Returns:
            str: Normalized string result.
        """
        raw = path.stem.replace("_", " ").replace("-", " ").strip()
        return " ".join(part.capitalize() for part in raw.split())
