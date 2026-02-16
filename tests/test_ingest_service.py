from pathlib import Path

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
