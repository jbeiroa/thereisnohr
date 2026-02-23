"""Application module `src.extract.service`."""

from dataclasses import dataclass

from src.extract.types import CandidateSignals, ExtractionDiagnostics, JobRequirements


@dataclass
class ExtractionService:
    """Represents ExtractionService."""

    def extract_sections(self, text: str) -> dict[str, str]:
        """Extract sections.

        Args:
            text: Input parameter.

        Returns:
            object: Computed result.

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
