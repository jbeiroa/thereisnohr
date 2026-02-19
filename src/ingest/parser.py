import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf4llm

from src.ingest.entities import ParsedResume


@dataclass
class PDFResumeParser:
    parser_version: str = "stage3.v1"

    def parse(self, path: Path) -> ParsedResume:
        markdown = self.extract_markdown(path)
        return self.parse_markdown(markdown=markdown, source_file=str(path))

    def parse_markdown(self, markdown: str, source_file: str) -> ParsedResume:
        clean_text, links = self.clean_resume_blocks(markdown)
        sections = self.extract_sections(markdown)
        language = self.detect_language(clean_text)

        return ParsedResume(
            source_file=source_file,
            raw_text=markdown,
            clean_text=clean_text,
            links=links,
            sections=sections,
            language=language,
            parser_version=self.parser_version,
        )

    def extract_markdown(self, path: Path) -> str:
        if not path.exists():
            raise FileNotFoundError(f"Resume not found: {path}")
        return pymupdf4llm.to_markdown(str(path), show_progress=False)

    # Adapted from legacy thereisnohr/data/handler.py with less destructive filtering.
    def clean_resume_blocks(self, text: str) -> tuple[str, list[str]]:
        extracted_links: list[str] = []
        unique_blocks: list[str] = []
        seen_blocks: set[str] = set()

        for block in self.split_by_blocks(text):
            links = re.findall(r"https?://[^\s\)\]]+", block)
            extracted_links.extend(links)

            if re.match(r"^[\-\s]+$", block):
                continue
            if len(block.split()) < 3:
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

    def split_by_blocks(self, text: str) -> list[str]:
        blocks = re.split(r"\n\n", text)
        cleaned: list[str] = []
        for block in blocks:
            normalized = re.sub(r"#+\s", "", block).lstrip("\n").strip()
            if normalized:
                cleaned.append(normalized)
        return cleaned

    def extract_sections(self, markdown: str) -> dict[str, str]:
        sections: dict[str, list[str]] = {}
        current = "general"
        sections[current] = []

        for line in markdown.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            heading = re.match(r"^#{1,6}\s+(.*)$", stripped)
            if heading:
                current = self._normalize_section_name(heading.group(1))
                sections.setdefault(current, [])
                continue

            sections.setdefault(current, []).append(stripped)

        out: dict[str, str] = {}
        for key, values in sections.items():
            section_text = "\n".join(values).strip()
            if section_text:
                out[key] = section_text

        if not out:
            out["general"] = markdown.strip()
        return out

    def detect_language(self, text: str) -> str:
        lowered = text.lower()
        english_markers = ["experience", "education", "skills", "teacher", "university"]
        spanish_markers = ["experiencia", "educacion", "habilidades", "docente", "universidad"]

        english_score = sum(1 for marker in english_markers if marker in lowered)
        spanish_score = sum(1 for marker in spanish_markers if marker in lowered)

        if english_score == 0 and spanish_score == 0:
            return "unknown"
        if english_score >= spanish_score:
            return "en"
        return "es"

    def _normalize_section_name(self, raw_name: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", raw_name.lower()).strip("_") or "general"
