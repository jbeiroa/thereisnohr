from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from tests.integration._helpers import assert_run_report_shape


@pytest.mark.integration
def test_flow_run_report_smoke(monkeypatch, integration_db_url, tmp_path: Path) -> None:
    import src.core.config as core_config

    core_config.get_settings.cache_clear()

    import src.storage.db as storage_db

    importlib.reload(storage_db)

    from src.ingest.pdf_ingestion_flow import ResumePdfIngestionFlow
    from src.ingest.parser import PDFResumeParser

    parser = PDFResumeParser()
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    c = tmp_path / "broken.pdf"
    a.write_text("x", encoding="utf-8")
    b.write_text("x", encoding="utf-8")
    c.write_text("x", encoding="utf-8")

    markdown_map = {
        str(a): "# John Doe\njdoe@example.com\n+1 415 555 0100\n# Experience\nA",
        str(b): "# John Doe\njdoe@example.com\n+1 415 555 0100\n# Skills\nPython",
    }

    def fake_parse_pdf(self, path: Path):
        if str(path) == str(c):
            raise ValueError("simulated parser failure")
        return parser.parse_markdown(markdown=markdown_map[str(path)], source_file=str(path))

    monkeypatch.setattr("src.ingest.service.IngestionService.parse_pdf", fake_parse_pdf)

    flow = ResumePdfIngestionFlow(use_cli=False)
    flow.input_dir = str(tmp_path)
    flow.pattern = "*.pdf"
    flow.next = lambda *args, **kwargs: None

    flow.start()
    flow.discover_files()

    branches = []
    for file_path in flow.pdf_files:
        branch = ResumePdfIngestionFlow(use_cli=False)
        branch.settings = flow.settings
        branch.input = file_path
        branch.next = lambda *args, **kwargs: None
        branch.ingest_one()
        branches.append(branch)

    flow.join_results(branches)
    flow.end()

    report = flow.run_report
    assert_run_report_shape(report)

    status_counts = report["status_counts"]
    assert status_counts.get("ingested", 0) >= 1
    assert status_counts.get("error", 0) == 1

    reasons = report["reason_breakdown"]
    assert reasons["error_types"].get("ValueError", 0) == 1

    file_rows = report["files"]
    assert any(row.get("status") == "error" for row in file_rows)
    assert report["files_sample_truncated"] == 0
