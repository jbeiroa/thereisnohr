from pathlib import Path

from pydantic import BaseModel

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

        def get_or_create_by_identity_key(
            self,
            *,
            identity_key,
            name=None,
            email=None,
            phone=None,
            links=None,
            name_confidence=None,
        ):
            existing = _Store.candidates.get(identity_key)
            if existing:
                if links:
                    existing["links"] = sorted(set((existing.get("links") or []) + list(links)))
                return type("Candidate", (), existing), False
            new_id = len(_Store.candidates) + 1
            candidate = {
                "id": new_id,
                "external_id": identity_key,
                "name": name,
                "email": email,
                "phone": phone,
                "links": list(links or []),
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
    assert sorted(_Store.candidates[next(iter(_Store.candidates))]["links"]) == []


def test_ingest_merges_candidate_links(monkeypatch) -> None:
    parser = PDFResumeParser()
    parsed_one = parser.parse_markdown(
        markdown="# John Doe\njdoe@example.com\n+1 415 555 0100\n# Projects\nhttps://a.example.com",
        source_file="/tmp/resume_one.pdf",
    )
    parsed_two = parser.parse_markdown(
        markdown="# John Doe\njdoe@example.com\n+1 415 555 0100\n# Projects\nhttps://b.example.com",
        source_file="/tmp/resume_two.pdf",
    )

    class _Store:
        candidates: dict[str, dict] = {}
        resumes: list[dict] = []

    class FakeCandidateRepository:
        def __init__(self, session):
            self.session = session

        def get_or_create_by_identity_key(self, *, identity_key, name=None, email=None, phone=None, links=None, name_confidence=None):
            existing = _Store.candidates.get(identity_key)
            if existing:
                existing["links"] = sorted(set((existing.get("links") or []) + list(links or [])))
                return type("Candidate", (), existing), False
            candidate = {
                "id": 1,
                "external_id": identity_key,
                "name": name,
                "email": email,
                "phone": phone,
                "links": list(links or []),
            }
            _Store.candidates[identity_key] = candidate
            return type("Candidate", (), candidate), True

    class FakeResumeRepository:
        def __init__(self, session):
            self.session = session

        def get_by_source_file(self, source_file):
            return None

        def get_by_content_hash(self, content_hash):
            return None

        def create(self, candidate_id, source_file, content_hash, raw_text, *, parsed_json=None, language=None):
            resume = {"id": len(_Store.resumes) + 1, "candidate_id": candidate_id}
            _Store.resumes.append(resume)
            return type("Resume", (), resume)

    class FakeResumeSectionRepository:
        def __init__(self, session):
            self.session = session

        def create(self, *, resume_id, section_type, content, metadata_json=None, tokens=None):
            return type("Section", (), {"resume_id": resume_id})

    monkeypatch.setattr("src.ingest.service.CandidateRepository", FakeCandidateRepository)
    monkeypatch.setattr("src.ingest.service.ResumeRepository", FakeResumeRepository)
    monkeypatch.setattr("src.ingest.service.ResumeSectionRepository", FakeResumeSectionRepository)
    parsed_iter = iter([parsed_one, parsed_two])
    service = IngestionService(enable_name_model_fallback=False, enable_section_model_fallback=False)
    monkeypatch.setattr(service, "parse_pdf", lambda path: next(parsed_iter))

    service.ingest_pdf(Path("/tmp/resume_one.pdf"), session=object())
    service.ingest_pdf(Path("/tmp/resume_two.pdf"), session=object())

    candidate = next(iter(_Store.candidates.values()))
    assert sorted(candidate["links"]) == ["https://a.example.com", "https://b.example.com"]


def test_section_model_promotion_applies_threshold(monkeypatch) -> None:
    parser = PDFResumeParser()
    parsed = parser.parse_markdown(
        markdown="# John Doe\njdoe@example.com\n+1 415 555 0100\n# Unknown Header\nPython SQL data pipelines",
        source_file="/tmp/resume.pdf",
    )

    class FakeLLM:
        def generate_structured(self, prompt: str, schema: type[BaseModel], model_alias: str, **kwargs):
            if "Classify resume section" in prompt:
                return schema.model_validate(
                    {"section_type": "skills", "confidence": 0.93, "reason": "contains skill terms"}
                )
            return schema.model_validate({"name": "John Doe", "confidence": 0.95, "reason": "header"})

        def embed(self, texts, embedding_model_alias):
            return []

    class _Store:
        candidates: dict[str, dict] = {}
        resumes: list[dict] = []
        sections: list[dict] = []

    class FakeCandidateRepository:
        def __init__(self, session):
            self.session = session

        def get_or_create_by_identity_key(self, **kwargs):
            candidate = {"id": 1, "external_id": kwargs["identity_key"], "links": kwargs.get("links")}
            _Store.candidates[kwargs["identity_key"]] = candidate
            return type("Candidate", (), candidate), True

    class FakeResumeRepository:
        def __init__(self, session):
            self.session = session

        def get_by_source_file(self, source_file):
            return None

        def get_by_content_hash(self, content_hash):
            return None

        def create(self, candidate_id, source_file, content_hash, raw_text, *, parsed_json=None, language=None):
            resume = {"id": 1, "candidate_id": candidate_id, "parsed_json": parsed_json}
            _Store.resumes.append(resume)
            return type("Resume", (), resume)

    class FakeResumeSectionRepository:
        def __init__(self, session):
            self.session = session

        def create(self, *, resume_id, section_type, content, metadata_json=None, tokens=None):
            row = {"resume_id": resume_id, "section_type": section_type, "metadata_json": metadata_json}
            _Store.sections.append(row)
            return type("Section", (), row)

    monkeypatch.setattr("src.ingest.service.CandidateRepository", FakeCandidateRepository)
    monkeypatch.setattr("src.ingest.service.ResumeRepository", FakeResumeRepository)
    monkeypatch.setattr("src.ingest.service.ResumeSectionRepository", FakeResumeSectionRepository)

    service = IngestionService(
        llm_client=FakeLLM(),
        enable_name_model_fallback=True,
        enable_section_model_fallback=True,
    )
    monkeypatch.setattr(service, "parse_pdf", lambda path: parsed)

    result = service.ingest_pdf(Path("/tmp/resume.pdf"), session=object())
    assert result.status == "ingested"
    assert any(section["section_type"] == "skills" for section in _Store.sections)
    assert _Store.sections[0]["metadata_json"]["original_section_type"] in {"contact", "general"}
    assert _Store.sections[-1]["metadata_json"]["section_routed_by_model"] is True
