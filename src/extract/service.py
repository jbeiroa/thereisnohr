"""Extraction-layer services and schemas for structured candidate/job signals."""

from dataclasses import dataclass

from src.extract.types import CandidateSignals, ExtractionDiagnostics, JobRequirements
from src.llm.client import LLMClient
from src.llm.errors import coerce_provider_exception


@dataclass
class ExtractionService:
    """Service object that orchestrates extraction workflow operations."""

    llm_client: LLMClient
    extractor_model_alias: str = "extractor_default"

    def extract_job_requirements(self, job_description: str) -> JobRequirements:
        """Extract structured job requirements from a job description string."""
        prompt = (
            "Extract structured job requirements from the following job description.\n"
            "Return JSON matching the schema.\n\n"
            f"Job Description:\n{job_description}"
        )
        try:
            return self.llm_client.generate_structured(
                prompt=prompt,
                schema=JobRequirements,
                model_alias=self.extractor_model_alias,
            )
        except Exception as e:
            raise coerce_provider_exception(e) from e

    def extract_candidate_signals(self, sections: dict[str, str]) -> CandidateSignals:
        """Extract structured candidate signals from parsed resume sections."""
        signals, _ = self.extract_with_diagnostics(sections)
        return signals

    def extract_with_diagnostics(self, sections: dict[str, str]) -> tuple[CandidateSignals, ExtractionDiagnostics]:
        """Extract candidate signals and return diagnostics metadata."""
        sections_text = "\n\n".join(f"--- {k.upper()} ---\n{v}" for k, v in sections.items() if v.strip())
        prompt = (
            "Extract structured candidate signals from the following parsed resume sections.\n"
            "Return JSON matching the schema.\n\n"
            f"Resume Sections:\n{sections_text}"
        )
        try:
            result, meta = self.llm_client.generate_structured_with_meta(
                prompt=prompt,
                schema=CandidateSignals,
                model_alias=self.extractor_model_alias,
            )
            
            diagnostics = ExtractionDiagnostics(
                model_alias=meta.model_alias,
                attempts=len(meta.attempts),
                fallback_used=meta.fallback_used,
                latency_ms=meta.latency_ms,
                prompt_tokens=meta.usage.prompt_tokens,
                completion_tokens=meta.usage.completion_tokens,
                total_tokens=meta.usage.total_tokens,
                estimated_cost_usd=meta.usage.estimated_cost_usd,
            )
            return result, diagnostics
        except Exception as e:
            raise coerce_provider_exception(e) from e
