from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.llm.client import LLMClient


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
    name: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""


class SectionFallbackResult(BaseModel):
    section_type: AllowedSectionType
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""


class LLMFallbackResolver:
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
        return self._llm.generate_structured(
            prompt=prompt,
            schema=NameFallbackResult,
            model_alias=self._model_alias,
            temperature=0.0,
        )

    def classify_section(
        self,
        *,
        raw_heading: str,
        content_excerpt: str,
        language: str | None,
    ) -> SectionFallbackResult:
        prompt = (
            "Classify resume section into one of these labels only: "
            "summary, experience, education, skills, projects, certifications, contact, general.\n"
            "Use heading and content. Favor contact when email/phone/link patterns exist.\n\n"
            f"language={language or 'unknown'}\n"
            f"heading={raw_heading!r}\n"
            f"content_excerpt={content_excerpt!r}\n"
            "Return JSON: {section_type, confidence, reason}."
        )
        return self._llm.generate_structured(
            prompt=prompt,
            schema=SectionFallbackResult,
            model_alias=self._model_alias,
            temperature=0.0,
        )
