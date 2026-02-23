from pathlib import Path

from src.ingest.parser import PDFResumeParser
from src.ingest.service import IngestionService


def test_discover_pdf_files_finds_nested(tmp_path: Path) -> None:
    (tmp_path / "a.pdf").write_text("x", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "b.pdf").write_text("x", encoding="utf-8")
    (nested / "ignore.txt").write_text("x", encoding="utf-8")

    service = IngestionService()
    files = service.discover_pdf_files(tmp_path)

    assert [path.name for path in files] == ["a.pdf", "b.pdf"]


def test_candidate_external_id_is_deterministic(tmp_path: Path) -> None:
    resume = tmp_path / "resume.pdf"
    resume.write_text("x", encoding="utf-8")

    service = IngestionService()
    first = service._build_candidate_external_id(resume)
    second = service._build_candidate_external_id(resume)

    assert first == second
    assert first.startswith("resume_file:")


def test_ingest_links_multiple_resumes_to_same_candidate(monkeypatch) -> None:
    parser = PDFResumeParser()
    parsed_one = parser.parse_markdown(
        markdown="# John Doe\njdoe@example.com\n+1 415 555 0100\n# Experience\nTeacher",
        source_file="/tmp/resume_one.pdf",
    )
    parsed_two = parser.parse_markdown(
        markdown="# John Doe\njdoe@example.com\n+1 415 555 0100\n# Skills\nPython",
        source_file="/tmp/resume_two.pdf",
    )

    class _Store:
        candidates: dict[str, dict] = {}
        resumes: list[dict] = []
        sections: list[dict] = []

    class FakeCandidateRepository:
        def __init__(self, session):
            self.session = session

        def get_or_create_by_identity_key(self, *, identity_key, name=None, email=None, phone=None):
            existing = _Store.candidates.get(identity_key)
            if existing:
                return type("Candidate", (), existing), False
            new_id = len(_Store.candidates) + 1
            candidate = {
                "id": new_id,
                "external_id": identity_key,
                "name": name,
                "email": email,
                "phone": phone,
            }
            _Store.candidates[identity_key] = candidate
            return type("Candidate", (), candidate), True

    class FakeResumeRepository:
        def __init__(self, session):
            self.session = session

        def get_by_source_file(self, source_file):
            for resume in _Store.resumes:
                if resume["source_file"] == source_file:
                    return type("Resume", (), resume)
            return None

        def get_by_content_hash(self, content_hash):
            for resume in _Store.resumes:
                if resume["content_hash"] == content_hash:
                    return type("Resume", (), resume)
            return None

        def create(self, candidate_id, source_file, content_hash, raw_text, *, parsed_json=None, language=None):
            resume = {
                "id": len(_Store.resumes) + 1,
                "candidate_id": candidate_id,
                "source_file": source_file,
                "content_hash": content_hash,
                "raw_text": raw_text,
                "parsed_json": parsed_json,
                "language": language,
            }
            _Store.resumes.append(resume)
            return type("Resume", (), resume)

    class FakeResumeSectionRepository:
        def __init__(self, session):
            self.session = session

        def create(self, *, resume_id, section_type, content, metadata_json=None, tokens=None):
            section = {
                "resume_id": resume_id,
                "section_type": section_type,
                "content": content,
                "metadata_json": metadata_json,
                "tokens": tokens,
            }
            _Store.sections.append(section)
            return type("Section", (), section)

    monkeypatch.setattr("src.ingest.service.CandidateRepository", FakeCandidateRepository)
    monkeypatch.setattr("src.ingest.service.ResumeRepository", FakeResumeRepository)
    monkeypatch.setattr("src.ingest.service.ResumeSectionRepository", FakeResumeSectionRepository)

    parsed_iter = iter([parsed_one, parsed_two])
    service = IngestionService()
    monkeypatch.setattr(service, "parse_pdf", lambda path: next(parsed_iter))

    first = service.ingest_pdf(Path("/tmp/resume_one.pdf"), session=object())
    second = service.ingest_pdf(Path("/tmp/resume_two.pdf"), session=object())

    assert first.status == "ingested"
    assert second.status == "ingested"
    assert first.candidate_id == second.candidate_id
    assert len(_Store.resumes) == 2
