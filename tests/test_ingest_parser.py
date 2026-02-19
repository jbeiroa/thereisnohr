from src.ingest.parser import PDFResumeParser


def test_clean_resume_blocks_extracts_unique_links_and_text() -> None:
    parser = PDFResumeParser()
    text = """
# John Doe

Experienced physics teacher.

Experienced physics teacher.

Portfolio: https://example.com/portfolio

---
"""
    clean_text, links = parser.clean_resume_blocks(text)

    assert "Experienced physics teacher." in clean_text
    assert len(clean_text.splitlines()) == 1
    assert links == ["https://example.com/portfolio"]


def test_extract_sections_from_markdown() -> None:
    parser = PDFResumeParser()
    markdown = """
# Experience
Taught Physics at School A

# Skills
Python
SQL
"""
    sections = parser.extract_sections(markdown)

    assert "experience" in sections
    assert "skills" in sections
    assert "Taught Physics" in sections["experience"]


def test_parse_markdown_detects_language() -> None:
    parser = PDFResumeParser()
    parsed = parser.parse_markdown(
        markdown="# Experiencia\nDocente de fisica con experiencia universitaria",
        source_file="resume.pdf",
    )

    assert parsed.source_file == "resume.pdf"
    assert parsed.language in {"es", "unknown"}
    assert parsed.parser_version == "stage3.v1"
