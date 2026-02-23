"""Application module `src.ingest.service`."""

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
from src.storage.repositories import CandidateRepository, ResumeRepository, ResumeSectionRepository


@dataclass(frozen=True)
class IngestionResult:
    """Represents IngestionResult."""

    status: str
    source_file: str
    candidate_id: int | None = None
    resume_id: int | None = None
    section_count: int = 0
    identity_confidence: float | None = None
    avg_section_confidence: float | None = None


@dataclass
class IngestionService:
    """Represents IngestionService."""

    parser: PDFResumeParser | None = None
    llm_client: LLMClient | None = None
    enable_name_model_fallback: bool | None = None
    enable_section_model_fallback: bool | None = None
    name_rule_trigger_threshold: float | None = None
    name_model_accept_threshold: float | None = None
    section_model_accept_threshold: float | None = None
    section_model_max_chars: int | None = None

    def __post_init__(self) -> None:
        """Helper for   post init  .

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
        """Run discover pdf files.

        Args:
            input_dir: Input parameter.
            pattern: Input parameter.

        Returns:
            object: Computed result.

        """
        if not input_dir.exists():
            raise FileNotFoundError(f"Input directory does not exist: {input_dir}")
        return sorted(path for path in input_dir.rglob(pattern) if path.is_file())

    def parse_pdf(self, path: Path) -> ParsedResume:
        """Run parse pdf.

        Args:
            path: Input parameter.

        Returns:
            object: Computed result.

        """
        assert self.parser is not None
        return self.parser.parse(path)

    def ingest_pdf(self, path: Path, session: Session) -> IngestionResult:
        """Run ingest pdf.

        Args:
            path: Input parameter.
            session: Input parameter.

        Returns:
            object: Computed result.

        """
        parsed = self.parse_pdf(path)
        resume_content_hash = compute_content_hash(parsed.clean_text)

        candidate_repo = CandidateRepository(session)
        resume_repo = ResumeRepository(session)
        section_repo = ResumeSectionRepository(session)

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
        for payload in section_payloads:
            section_repo.create(
                resume_id=resume.id,
                section_type=payload["section_type"],
                content=payload["content"],
                metadata_json=payload["metadata_json"],
                tokens=len(payload["content"].split()),
            )
            section_count += 1
            section_confidences.append(payload["metadata_json"]["section_confidence"])

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
        """Helper for  build section payloads.

        Args:
            parsed: Input parameter.
            resume_id: Input parameter.

        Returns:
            object: Computed result.

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
        """Helper for  should route section.

        Args:
            section_type: Input parameter.
            confidence: Input parameter.

        Returns:
            bool: True when the condition is met.

        """
        return section_type == "general" or confidence < float(self.section_model_accept_threshold or 0.75)

    def _build_llm_fallback_resolver(self) -> LLMFallbackResolver | None:
        """Helper for  build llm fallback resolver.

        Returns:
            object: Computed result.

        """
        client = self.llm_client
        if client is None:
            try:
                client = build_default_llm_client()
            except Exception:
                return None
        return LLMFallbackResolver(client)

    def _build_candidate_external_id(self, path: Path) -> str:
        """Helper for  build candidate external id.

        Args:
            path: Input parameter.

        Returns:
            object: Computed result.

        """
        digest = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:16]
        return f"resume_file:{digest}"

    def _infer_candidate_name(self, path: Path) -> str:
        """Helper for  infer candidate name.

        Args:
            path: Input parameter.

        Returns:
            object: Computed result.

        """
        raw = path.stem.replace("_", " ").replace("-", " ").strip()
        return " ".join(part.capitalize() for part in raw.split())
