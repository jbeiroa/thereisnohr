from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.ingest.parser import PDFResumeParser
from src.storage import models


@dataclass
class MappingParser:
    mapping: dict[str, str]

    def parse(self, path: Path):
        markdown = self.mapping[str(path)]
        parser = PDFResumeParser()
        return parser.parse_markdown(markdown=markdown, source_file=str(path))


def counts(session) -> dict[str, int]:
    return {
        "candidates": session.query(models.Candidate).count(),
        "resumes": session.query(models.Resume).count(),
        "sections": session.query(models.ResumeSection).count(),
    }


def assert_run_report_shape(report: dict) -> None:
    required = {
        "run_meta",
        "status_counts",
        "step_timing_summary",
        "ingest_quality",
        "reason_breakdown",
        "files",
    }
    missing = required.difference(report.keys())
    assert not missing, f"Missing run_report keys: {sorted(missing)}"
