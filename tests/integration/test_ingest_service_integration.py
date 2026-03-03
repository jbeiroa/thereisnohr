from __future__ import annotations

from pathlib import Path

import pytest

from src.ingest.service import IngestionService
from src.llm.types import LLMCallMetadata
from src.storage import models
from tests.integration._helpers import MappingParser, counts


@pytest.mark.integration
def test_candidate_identity_reuse_across_files(db_session, tmp_path: Path) -> None:
    first_path = tmp_path / "a.pdf"
    second_path = tmp_path / "b.pdf"

    parser = MappingParser(
        {
            str(first_path): "# John Doe\njdoe@example.com\n+1 415 555 0100\n# Experience\nTaught physics",
            str(second_path): "# John Doe\njdoe@example.com\n+1 415 555 0100\n# Skills\nPython\nSQL",
        }
    )
    service = IngestionService(parser=parser)

    r1 = service.ingest_pdf(first_path, db_session)
    db_session.commit()
    r2 = service.ingest_pdf(second_path, db_session)
    db_session.commit()

    assert r1.status == "ingested"
    assert r2.status == "ingested"
    assert r1.candidate_id == r2.candidate_id

    db_counts = counts(db_session)
    assert db_counts["candidates"] == 1
    assert db_counts["resumes"] == 2

    candidate = db_session.query(models.Candidate).one()
    assert candidate.external_id.startswith("candidate:v2:email:")
    assert isinstance(candidate.links, list)

    resume = db_session.query(models.Resume).filter(models.Resume.id == r1.resume_id).one()
    parsed = resume.parsed_json or {}
    identity = parsed.get("identity") or {}
    assert isinstance(identity.get("confidence"), float)


@pytest.mark.integration
def test_skip_by_source_file(db_session, tmp_path: Path) -> None:
    source_path = tmp_path / "resume.pdf"
    parser = MappingParser(
        {
            str(source_path): "# John Doe\njdoe@example.com\n+1 415 555 0100\n# Experience\nA",
        }
    )
    service = IngestionService(parser=parser)

    first = service.ingest_pdf(source_path, db_session)
    db_session.commit()
    second = service.ingest_pdf(source_path, db_session)
    db_session.commit()

    assert first.status == "ingested"
    assert second.status == "skipped_existing_resume"
    assert counts(db_session)["resumes"] == 1


@pytest.mark.integration
def test_skip_by_content_hash(db_session, tmp_path: Path) -> None:
    first_path = tmp_path / "resume_1.pdf"
    second_path = tmp_path / "resume_2.pdf"
    markdown = "# John Doe\njdoe@example.com\n+1 415 555 0100\n# Experience\nA"

    parser = MappingParser(
        {
            str(first_path): markdown,
            str(second_path): markdown,
        }
    )
    service = IngestionService(parser=parser)

    first = service.ingest_pdf(first_path, db_session)
    db_session.commit()
    second = service.ingest_pdf(second_path, db_session)
    db_session.commit()

    assert first.status == "ingested"
    assert second.status == "skipped_existing_content"

    resumes = db_session.query(models.Resume).all()
    assert len(resumes) == 1
    assert resumes[0].content_hash is not None


@pytest.mark.integration
def test_fallback_identity_path(db_session, tmp_path: Path) -> None:
    source_path = tmp_path / "fallback.pdf"
    parser = MappingParser(
        {
            str(source_path): "# Experience\nWorked on curriculum projects and tutoring.",
        }
    )
    service = IngestionService(parser=parser)

    result = service.ingest_pdf(source_path, db_session)
    db_session.commit()

    assert result.status == "ingested"
    candidate = db_session.query(models.Candidate).one()
    assert candidate.external_id.startswith("resume_content:")

    resume = db_session.query(models.Resume).one()
    identity = (resume.parsed_json or {}).get("identity") or {}
    confidence = identity.get("confidence")
    assert isinstance(confidence, float)
    assert confidence <= 0.4


@pytest.mark.integration
def test_section_diagnostics_persisted(db_session, tmp_path: Path) -> None:
    source_path = tmp_path / "diag.pdf"
    parser = MappingParser(
        {
            str(source_path): "# Unknown Header\ncontact@example.com\n+1 415 555 0100",
        }
    )
    service = IngestionService(parser=parser)

    result = service.ingest_pdf(source_path, db_session)
    db_session.commit()

    assert result.status == "ingested"
    section = db_session.query(models.ResumeSection).one()
    metadata = section.metadata_json or {}
    assert "section_confidence" in metadata
    assert "diagnostic_flags" in metadata
    assert "recategorization_candidate" in metadata
    assert "original_section_type" in metadata
    assert "section_routed_by_model" in metadata


@pytest.mark.integration
def test_non_skill_section_embeddings_persisted(db_session, tmp_path: Path) -> None:
    source_path = tmp_path / "embed.pdf"
    parser = MappingParser(
        {
            str(source_path): "# Experience\nBuilt services for backend systems.\n# Skills\nPython\nSQL",
        }
    )

    class FakeLLM:
        def embed_with_meta(self, texts, embedding_model_alias):
            vectors = [[0.1] * 1536 for _ in texts]
            meta = LLMCallMetadata(
                model_alias=embedding_model_alias,
                selected_model="openai/text-embedding-3-small",
            )
            return vectors, meta

    service = IngestionService(
        parser=parser,
        llm_client=FakeLLM(),
        enable_name_model_fallback=False,
        enable_section_model_fallback=False,
    )

    result = service.ingest_pdf(source_path, db_session)
    db_session.commit()

    assert result.status == "ingested"
    sections = db_session.query(models.ResumeSection).all()
    non_skill_ids = {row.id for row in sections if row.section_type != "skills" and row.content.strip()}
    skill_ids = {row.id for row in sections if row.section_type == "skills"}

    embeddings = db_session.query(models.Embedding).all()
    assert len(embeddings) == len(non_skill_ids)
    assert {row.owner_type for row in embeddings} == {"resume_section"}
    assert {row.owner_id for row in embeddings} == non_skill_ids
    assert not ({row.owner_id for row in embeddings} & skill_ids)
