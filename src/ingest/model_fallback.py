"""Ingestion components for parsing resumes and persisting structured ATS artifacts."""

from typing import Literal, TypeVar

from pydantic import BaseModel, Field

from src.llm.client import LLMClient
from src.llm.errors import coerce_provider_exception

SchemaModelT = TypeVar("SchemaModelT", bound=BaseModel)


AllowedSectionType = Literal[
    "summary",
    "experience",
    "education",
    "skills",
    "projects",
    "certifications",
    "contact",
    "general",
]


class NameFallbackResult(BaseModel):
    """Result shape for name fallback resolution."""

    name: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""


class SectionFallbackResult(BaseModel):
    """Result shape for section fallback classification."""

    section_type: AllowedSectionType
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""


class LLMFallbackResolver:
    """Data model for llmfallbackresolver values."""

    def __init__(self, llm_client: LLMClient, *, model_alias: str = "extractor_default") -> None:
        self._llm = llm_client
        self._model_alias = model_alias

    def resolve_name(
        self,
        *,
        candidate_lines: list[str],
        emails: list[str],
        phones: list[str],
        language: str | None,
    ) -> NameFallbackResult:
        """Resolve the most likely candidate name from header context."""
        prompt = (
            "Extract the most likely person full name from resume header lines.\n"
            "Rules:\n"
            "- Prefer real person names (2-4 tokens).\n"
            "- Reject locations, skills, roles, and section titles.\n"
            "- If uncertain, return null name and low confidence.\n\n"
            f"language={language or 'unknown'}\n"
            f"emails={emails}\n"
            f"phones={phones}\n"
            f"candidate_lines={candidate_lines}\n"
            "Return JSON: {name, confidence, reason}."
        )
        return self._generate(prompt=prompt, schema=NameFallbackResult)

    def classify_section(
        self,
        *,
        raw_heading: str,
        content_excerpt: str,
        language: str | None,
    ) -> SectionFallbackResult:
        """Classify an ambiguous section into one allowed section label."""
        prompt = (
            "Classify resume section into one of these labels only: "
            "summary, experience, education, skills, projects, certifications, contact, general.\n"
            "Use heading and content. Favor contact when email/phone/link patterns exist.\n\n"
            f"language={language or 'unknown'}\n"
            f"heading={raw_heading!r}\n"
            f"content_excerpt={content_excerpt!r}\n"
            "Return JSON: {section_type, confidence, reason}."
        )
        return self._generate(prompt=prompt, schema=SectionFallbackResult)

    def _generate(self, *, prompt: str, schema: type[SchemaModelT]) -> SchemaModelT:
        """Helper that handles generate.

        Args:
            prompt (str): Prompt sent to the language model.
            schema (type[SchemaModelT]): Pydantic model used to validate structured response payload.

        Returns:
            SchemaModelT: Return value for this function.

        Raises:
            normalized: Raised when validation or execution constraints are violated.
        """
        try:
            return self._llm.generate_structured(
                prompt=prompt,
                schema=schema,
                model_alias=self._model_alias,
                temperature=0.0,
            )
        except Exception as exc:
            normalized = coerce_provider_exception(exc)
            if normalized is not exc:
                raise normalized from exc
            raise
