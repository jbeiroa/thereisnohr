import hashlib
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from src.ingest.parser import PDFResumeParser
from src.ingest.entities import ParsedResume
from src.storage.repositories import CandidateRepository, ResumeRepository, ResumeSectionRepository


@dataclass(frozen=True)
class IngestionResult:
    status: str
    source_file: str
    candidate_id: int | None = None
    resume_id: int | None = None
    section_count: int = 0


@dataclass
class IngestionService:
    parser: PDFResumeParser | None = None

    def __post_init__(self) -> None:
        if self.parser is None:
            self.parser = PDFResumeParser()

    def discover_pdf_files(self, input_dir: Path, pattern: str = "*.pdf") -> list[Path]:
        if not input_dir.exists():
            raise FileNotFoundError(f"Input directory does not exist: {input_dir}")
        return sorted(path for path in input_dir.rglob(pattern) if path.is_file())

    def parse_pdf(self, path: Path) -> ParsedResume:
        assert self.parser is not None
        return self.parser.parse(path)

    def ingest_pdf(self, path: Path, session: Session) -> IngestionResult:
        parsed = self.parse_pdf(path)

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

        candidate_external_id = self._build_candidate_external_id(path)
        candidate_name = self._infer_candidate_name(path)
        candidate, _ = candidate_repo.get_or_create_by_external_id(
            external_id=candidate_external_id,
            name=candidate_name,
        )

        resume = resume_repo.create(
            candidate_id=candidate.id,
            source_file=parsed.source_file,
            raw_text=parsed.raw_text,
            parsed_json={
                "clean_text": parsed.clean_text,
                "links": parsed.links,
                "parser_version": parsed.parser_version,
                "section_names": list(parsed.sections.keys()),
            },
            language=parsed.language,
        )

        section_count = 0
        for section_type, content in parsed.sections.items():
            section_repo.create(
                resume_id=resume.id,
                section_type=section_type,
                content=content,
                metadata_json={"parser_version": parsed.parser_version},
                tokens=len(content.split()),
            )
            section_count += 1

        return IngestionResult(
            status="ingested",
            source_file=parsed.source_file,
            candidate_id=candidate.id,
            resume_id=resume.id,
            section_count=section_count,
        )

    def _build_candidate_external_id(self, path: Path) -> str:
        digest = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:16]
        return f"resume_file:{digest}"

    def _infer_candidate_name(self, path: Path) -> str:
        raw = path.stem.replace("_", " ").replace("-", " ").strip()
        return " ".join(part.capitalize() for part in raw.split())
