"""Extraction-layer services and schemas for structured candidate/job signals."""

from dataclasses import dataclass

from src.extract.types import CandidateSignals, ExtractionDiagnostics, JobRequirements


@dataclass
class ExtractionService:
    """Service object that orchestrates extraction workflow operations."""

    def extract_sections(self, text: str) -> dict[str, str]:
        """Extracts structured data from raw resume or markdown input.

        Args:
            text (str): Text input being parsed, normalized, or scored.

        Returns:
            dict[str, str]: Return value for this function.
        """
        return {"raw": text}

    def extract_job_requirements(self, job_description: str) -> JobRequirements:
        """Extract structured job requirements from a job description string."""
        _ = job_description
        raise NotImplementedError("Job requirements extraction is not implemented yet.")

    def extract_candidate_signals(self, resume_text: str) -> CandidateSignals:
        """Extract structured candidate signals from resume text."""
        _ = resume_text
        raise NotImplementedError("Candidate signal extraction is not implemented yet.")

    def extract_with_diagnostics(self, resume_text: str) -> tuple[CandidateSignals, ExtractionDiagnostics]:
        """Extract candidate signals and return diagnostics metadata."""
        _ = resume_text
        raise NotImplementedError("Extraction with diagnostics is not implemented yet.")
