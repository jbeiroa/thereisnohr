"""Tests for extraction type scaffolding."""

from src.extract.types import CandidateSignals, ExtractionDiagnostics, JobRequirements


def test_extract_type_defaults() -> None:
    """Verify extract-related models have safe defaults."""
    req = JobRequirements()
    sig = CandidateSignals()
    diag = ExtractionDiagnostics(model_alias="extractor_default")
    assert req.hard_skills == []
    assert sig.skills == []
    assert diag.attempts == 0
