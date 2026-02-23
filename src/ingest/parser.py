"""Application module `src.ingest.parser`."""

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pymupdf
import pymupdf4llm

from src.ingest.entities import HeadingSpan, ParsedResume, SectionItem

SECTION_MAPPING = {
    # -------------------
    # SUMMARY
    # -------------------
    "summary": "summary",
    "professional summary": "summary",
    "executive summary": "summary",
    "profile": "summary",
    "professional profile": "summary",
    "about": "summary",
    "about me": "summary",
    "sobre mi": "summary",
    "sobre mí": "summary",
    "career summary": "summary",
    "objective": "summary",
    "career objective": "summary",
    "personal statement": "summary",
    "overview": "summary",

    # -------------------
    # EXPERIENCE
    # -------------------
    "experience": "experience",
    "professional experience": "experience",
    "work experience": "experience",
    "employment history": "experience",
    "work history": "experience",
    "career history": "experience",
    "employment": "experience",
    "professional background": "experience",
    "relevant experience": "experience",
    "industry experience": "experience",
    "internship experience": "experience",
    "internships": "experience",
    "positions held": "experience",
    "experiencia": "experience",
    "experiencia profesional": "experience",
    "experiencia laboral": "experience",

    # -------------------
    # EDUCATION
    # -------------------
    "education": "education",
    "academic background": "education",
    "academic history": "education",
    "academic experience": "education",
    "qualifications": "education",
    "academic qualifications": "education",
    "degrees": "education",
    "degree": "education",
    "studies": "education",
    "formal education": "education",
    "courses": "education",
    "coursework": "education",
    "relevant coursework": "education",
    "training": "education",
    "educacion": "education",
    "educación": "education",
    "formacion": "education",
    "formación": "education",

    # -------------------
    # SKILLS
    # -------------------
    "skills": "skills",
    "technical skills": "skills",
    "core skills": "skills",
    "key skills": "skills",
    "professional skills": "skills",
    "hard skills": "skills",
    "soft skills": "skills",
    "competencies": "skills",
    "core competencies": "skills",
    "expertise": "skills",
    "technical expertise": "skills",
    "technologies": "skills",
    "tech stack": "skills",
    "tools": "skills",
    "informatica": "skills",
    "informática": "skills",
    "habilidades": "skills",
    "competencias": "skills",
    "aptitudes": "skills",

    # -------------------
    # PROJECTS
    # -------------------
    "projects": "projects",
    "personal projects": "projects",
    "academic projects": "projects",
    "professional projects": "projects",
    "selected projects": "projects",
    "key projects": "projects",
    "portfolio": "projects",
    "research projects": "projects",
    "proyectos": "projects",

    # -------------------
    # CERTIFICATIONS
    # -------------------
    "certifications": "certifications",
    "certification": "certifications",
    "licenses": "certifications",
    "licenses and certifications": "certifications",
    "professional certifications": "certifications",
    "credentials": "certifications",
    "accreditations": "certifications",
    "certificaciones": "certifications",
    "licencias": "certifications",

    # -------------------
    # CONTACT
    # -------------------
    "contact": "contact",
    "contact information": "contact",
    "personal information": "contact",
    "personal details": "contact",
    "contact details": "contact",
    "get in touch": "contact",
    "contact me": "contact",
    "contacto": "contact",
    "informacion de contacto": "contact",
    "información de contacto": "contact",
    "idiomas": "skills",
    "languages": "skills",
    "publications": "projects",
    "publicaciones": "projects",
}


@dataclass
class PDFResumeParser:
    """Represents PDFResumeParser."""

    parser_version: str = "stage3.v1"

    def parse(self, path: Path) -> ParsedResume:
        """Run parse.

        Args:
            path: Input parameter.

        Returns:
            object: Computed result.

        """
        markdown = self.extract_markdown(path)
        return self.parse_markdown(markdown=markdown, source_file=str(path))

    def parse_markdown(self, markdown: str, source_file: str) -> ParsedResume:
        """Run parse markdown.

        Args:
            markdown: Input parameter.
            source_file: Input parameter.

        Returns:
            object: Computed result.

        """
        clean_markdown = self._preclean_markdown(markdown)
        clean_text, _ = self.clean_resume_blocks(clean_markdown)
        links = self.extract_links(clean_markdown)
        spans = self._find_heading_spans(clean_markdown)
        for i, span in enumerate(spans):
            spans[i] = HeadingSpan(
                raw_heading=span.raw_heading,
                title=self._map_heading_to_section(span.raw_heading),
                start_line=span.start_line,
                end_line=span.end_line,
            )
        spans = self._absorb_generals_into_single_line_sections(spans)
        sections, section_items = self._extract_sections_and_items(clean_markdown, spans)
        language = self.detect_language(clean_markdown)

        return ParsedResume(
            source_file=source_file,
            raw_text=markdown,
            clean_text=clean_text,
            links=links,
            sections=sections,
            section_items=section_items,
            language=language,
            parser_version=self.parser_version,
        )

    def extract_markdown(self, path: Path) -> str:
        """Extract markdown.

        Args:
            path: Input parameter.

        Returns:
            object: Computed result.

        """
        if not path.exists():
            raise FileNotFoundError(f"Resume not found: {path}")
        doc = pymupdf.open(path)
        return pymupdf4llm.to_markdown(doc, show_progress=False)

    def split_by_blocks(self, text: str) -> list[str]:
        """Run split by blocks.

        Args:
            text: Input parameter.

        Returns:
            object: Computed result.

        """
        blocks = re.split(r"\n\n", text)
        cleaned: list[str] = []
        for block in blocks:
            normalized = re.sub(r"#+\s", "", block).lstrip("\n").strip()
            if normalized:
                cleaned.append(normalized)
        return cleaned

    def clean_resume_blocks(self, text: str) -> tuple[str, list[str]]:
        """Run clean resume blocks.

        Args:
            text: Input parameter.

        Returns:
            object: Computed result.

        """
        extracted_links: list[str] = []
        unique_blocks: list[str] = []
        seen_blocks: set[str] = set()

        for block in self.split_by_blocks(text):
            links = re.findall(r"https?://[^\s\)\]]+", block)
            extracted_links.extend(links)

            if re.match(r"^[\-\s]+$", block):
                continue

            cleaned_block = re.sub(r"https?://[^\s\)\]]+", "", block).strip()
            cleaned_block = re.sub(r"\[([^\[\]]+)\]\s*\(\s*\)", r"\1", cleaned_block).strip()
            normalized_block = " ".join(cleaned_block.splitlines()).strip()

            if normalized_block and normalized_block not in seen_blocks:
                seen_blocks.add(normalized_block)
                unique_blocks.append(normalized_block)

        text_out = "\n".join(unique_blocks)
        unique_links = sorted(set(extracted_links))
        return text_out, unique_links

    def extract_links(self, text: str) -> list[str]:
        """Extract links.

        Args:
            text: Input parameter.

        Returns:
            object: Computed result.

        """
        links = re.findall(r"https?://[^\s\)\]]+", text)
        return sorted(set(links))

    def extract_sections(self, markdown: str, spans: list[HeadingSpan] | None = None) -> dict[str, str]:
        """Extract sections.

        Args:
            markdown: Input parameter.
            spans: Input parameter.

        Returns:
            object: Computed result.

        """
        if spans is None:
            mapped_spans: list[HeadingSpan] = []
            for span in self._find_heading_spans(markdown):
                mapped_spans.append(
                    HeadingSpan(
                        raw_heading=span.raw_heading,
                        title=self._map_heading_to_section(span.raw_heading),
                        start_line=span.start_line,
                        end_line=span.end_line,
                    )
                )
            spans = self._absorb_generals_into_single_line_sections(mapped_spans)

        sections, _ = self._extract_sections_and_items(markdown, spans)
        return sections

    def _extract_sections_and_items(
        self, markdown: str, spans: list[HeadingSpan]
    ) -> tuple[dict[str, str], list[SectionItem]]:
        """Helper for  extract sections and items.

        Args:
            markdown: Input parameter.
            spans: Input parameter.

        Returns:
            object: Computed result.

        """
        lines = markdown.splitlines()
        sections: dict[str, str] = {}
        items: list[SectionItem] = []

        for span in spans:
            if span.start_line >= len(lines):
                continue

            content_lines = lines[span.start_line + 1 : span.end_line + 1]
            content = "\n".join(line.strip() for line in content_lines if line.strip()).strip()
            if not content:
                continue

            if span.title in sections:
                sections[span.title] = f"{sections[span.title]}\n\n{content}"
            else:
                sections[span.title] = content

            items.append(
                SectionItem(
                    raw_heading=span.raw_heading,
                    normalized_type=span.title,
                    content=content,
                    confidence=1.0 if span.title != "general" else 0.5,
                    signals=self._build_section_signals(
                        normalized_type=span.title,
                        raw_heading=span.raw_heading,
                        content=content,
                    ),
                )
            )

        if not sections:
            fallback = markdown.strip()
            if fallback:
                sections["general"] = fallback
                items.append(
                    SectionItem(
                        raw_heading="",
                        normalized_type="general",
                        content=fallback,
                        confidence=0.3,
                        signals=self._build_section_signals(
                            normalized_type="general",
                            raw_heading="",
                            content=fallback,
                        ),
                    )
                )

        return sections, items

    def detect_language(self, text: str) -> str:
        """Run detect language.

        Args:
            text: Input parameter.

        Returns:
            object: Computed result.

        """
        lowered = text.lower()
        english_markers = ["experience", "education", "skills", "university"]
        spanish_markers = ["experiencia", "educación", "habilidades", "universidad"]

        english_score = sum(1 for marker in english_markers if marker in lowered)
        spanish_score = sum(1 for marker in spanish_markers if marker in lowered)

        if english_score == 0 and spanish_score == 0:
            return "unknown"
        if english_score >= spanish_score:
            return "en"
        return "es"

    def _remove_omitted_pictures(self, markdown: str) -> str:
        """Helper for  remove omitted pictures.

        Args:
            markdown: Input parameter.

        Returns:
            object: Computed result.

        """
        return re.sub(
            r"\*\*==>.*?<==\*\*",
            "",
            markdown,
            flags=re.DOTALL
        )

    def _remove_encoding_artifacts(self, markdown: str) -> str:
        """
        Removes common encoding mismatch artifacts such as
        the Unicode replacement character (�).
        """
        return markdown.replace("\uFFFD", "")

    def _clean_markdown_table_artifacts(self, text: str) -> str:
        """
        Cleans flattened markdown tables into readable plain text.
        """

        lines = text.splitlines()
        cleaned_lines = []

        for line in lines:
            line = line.strip()

            # Skip separator rows like |---|---|
            if re.fullmatch(r"\|?\s*-+\s*(\|\s*-+\s*)+\|?", line):
                continue

            # Remove leading/trailing pipes
            line = line.strip("|")

            # Replace remaining pipes with a readable separator
            line = re.sub(r"\s*\|\s*", " - ", line)

            # Remove accidental double separators
            line = re.sub(r"-\s*-", "-", line)

            # Remove trailing double pipes
            line = re.sub(r"\|\|+$", "", line)

            line = line.strip()

            if line:
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _remove_all_bullet_chars(self, text: str) -> str:
        """Helper for  remove all bullet chars.

        Args:
            text: Input parameter.

        Returns:
            object: Computed result.

        """
        bullet_chars = r"[\u2022\u25AA\u25E6\u2023\u00B7]"
        return re.sub(bullet_chars, "", text)

    def _remove_dotted_leaders(self, text: str) -> str:
        """
        Removes long sequences of spaced dots like:
        . . . . . . . . . .
        but keeps normal sentence punctuation.
        """
        # Match: dot + space repeated at least 3 times
        pattern = r"(?:\.\s*){3,}"
        return re.sub(pattern, "", text)

    def _preclean_markdown(self, markdown: str) -> str:
        """Helper for  preclean markdown.

        Args:
            markdown: Input parameter.

        Returns:
            object: Computed result.

        """
        clean_markdown=self._remove_omitted_pictures(markdown)
        clean_markdown=self._remove_encoding_artifacts(clean_markdown)
        clean_markdown=self._clean_markdown_table_artifacts(clean_markdown)
        clean_markdown=self._remove_all_bullet_chars(clean_markdown)
        clean_markdown=self._remove_dotted_leaders(clean_markdown)
        return clean_markdown

    def _find_heading_spans(self, markdown: str) -> list[HeadingSpan]:
        """Helper for  find heading spans.

        Args:
            markdown: Input parameter.

        Returns:
            object: Computed result.

        """
        lines = markdown.splitlines()
        heading_pattern = re.compile(r"^(#{1,6})\s+(.*)")

        spans: list[HeadingSpan] = []
        current_span: HeadingSpan | None = None

        for i, line in enumerate(lines):
            match = heading_pattern.match(line)

            if match:
                # Close previous span
                if current_span is not None:
                    current_span.end_line = i - 1
                    spans.append(current_span)

                # Start new span
                title = match.group(2).strip()
                current_span = HeadingSpan(
                    raw_heading=title,
                    title=title,
                    start_line=i,
                    end_line=-1     # temporary placeholder
                )

        # Close last span
        if current_span is not None:
            current_span.end_line = len(lines) - 1
            spans.append(current_span)

        return spans

    def _map_heading_to_section(self, title: str) -> str:
        """Helper for  map heading to section.

        Args:
            title: Input parameter.

        Returns:
            object: Computed result.

        """
        normalized = self._normalize_heading_text(title)
        normalized = " ".join(normalized.split())

        for key, value in SECTION_MAPPING.items():
            if key in normalized:
                return value

        return "general"

    def _normalize_heading_text(self, title: str) -> str:
        """Helper for  normalize heading text.

        Args:
            title: Input parameter.

        Returns:
            object: Computed result.

        """
        no_markdown = re.sub(r"[*_`~]+", " ", title)
        folded = unicodedata.normalize("NFKD", no_markdown)
        folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
        return re.sub(r"[^a-z0-9\s]+", " ", folded.lower())

    def _build_section_signals(
        self,
        *,
        normalized_type: str,
        raw_heading: str,
        content: str,
    ) -> dict:
        """Helper for  build section signals.

        Args:
            normalized_type: Input parameter.
            raw_heading: Input parameter.
            content: Input parameter.

        Returns:
            object: Computed result.

        """
        flags: list[str] = []
        heading_mapped_to_general = bool(raw_heading.strip()) and normalized_type == "general"
        if heading_mapped_to_general:
            flags.append("heading_unknown")
        if len(content.split()) < 8:
            flags.append("short_content")
        if self._looks_like_contact_block(content):
            flags.append("looks_like_contact_block")

        recat = self._suggest_recategorization(
            normalized_type=normalized_type,
            content=content,
            has_contact_hint="looks_like_contact_block" in flags,
        )

        confidence_inputs = {
            "word_count": len(content.split()),
            "heading_mapped_to_general": heading_mapped_to_general,
        }

        return {
            "diagnostic_flags": flags,
            "confidence_inputs": confidence_inputs,
            "recategorization_candidate": recat,
        }

    def _looks_like_contact_block(self, content: str) -> bool:
        """Helper for  looks like contact block.

        Args:
            content: Input parameter.

        Returns:
            bool: True when the condition is met.

        """
        lowered = content.lower()
        has_email = bool(re.search(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}", lowered))
        has_phone = bool(re.search(r"(?:\+?\d[\d\s().\-/]{6,}\d)", content))
        return has_email or has_phone

    def _suggest_recategorization(
        self,
        *,
        normalized_type: str,
        content: str,
        has_contact_hint: bool,
    ) -> dict | None:
        """Helper for  suggest recategorization.

        Args:
            normalized_type: Input parameter.
            content: Input parameter.
            has_contact_hint: Input parameter.

        Returns:
            object: Computed result.

        """
        lowered = content.lower()
        if normalized_type != "general":
            return None

        if has_contact_hint:
            return {"section_type": "contact", "confidence": 0.8}

        keyword_buckets = {
            "skills": ["python", "sql", "java", "skills", "technologies", "stack"],
            "experience": ["experience", "responsible", "led", "worked", "managed"],
            "contact": ["email", "phone", "linkedin", "github"],
        }
        for target, keywords in keyword_buckets.items():
            hits = sum(1 for keyword in keywords if keyword in lowered)
            if hits >= 2:
                return {"section_type": target, "confidence": 0.65}
        return None

    def _absorb_generals_into_single_line_sections(
            self,
            spans: list[HeadingSpan],
        ) -> list[HeadingSpan]:
        """
        If a non-'general' section has only one line (start_line == end_line),
        absorb consecutive following 'general' sections into it.
        """

        result: list[HeadingSpan] = []
        i = 0

        while i < len(spans):
            current = spans[i]

            # Only apply rule to non-general single-line sections
            if (
                current.title != "general"
                and current.start_line == current.end_line
            ):
                j = i + 1

                # Absorb consecutive general sections
                while j < len(spans) and spans[j].title == "general":
                    current.end_line = spans[j].end_line
                    j += 1

                result.append(current)
                i = j  # Skip absorbed spans

            else:
                result.append(current)
                i += 1

        return result
