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
    assert len(clean_text.splitlines()) >= 1
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
    assert "Python" in sections["skills"]


def test_absorb_general_sections_into_single_line_non_general_heading() -> None:
    parser = PDFResumeParser()
    markdown = """## Skills
Python
SQL
## Experience
## Advisor to the Secretary General
Led data collection and analysis.
Improved policy outcomes.
## Education
BSc Physics
"""
    sections = parser.extract_sections(markdown)

    assert "experience" in sections
    assert "Led data collection and analysis." in sections["experience"]
    assert "Improved policy outcomes." in sections["experience"]
    assert "skills" in sections
    assert "education" in sections


def test_parse_markdown_detects_language() -> None:
    parser = PDFResumeParser()
    parsed = parser.parse_markdown(
        markdown="# Experiencia\nDocente de fisica con experiencia universitaria",
        source_file="resume.pdf",
    )

    assert parsed.source_file == "resume.pdf"
    assert parsed.language in {"es", "unknown"}
    assert parsed.parser_version == "stage3.v1"
    assert parsed.sections["experience"].startswith("Docente")
    assert parsed.section_items


def test_parse_markdown_extracts_links_in_output() -> None:
    parser = PDFResumeParser()
    parsed = parser.parse_markdown(
        markdown="# Projects\nSee https://example.com/project and https://example.com/project",
        source_file="resume.pdf",
    )

    assert parsed.links == ["https://example.com/project"]


def test_parse_markdown_populates_section_diagnostics() -> None:
    parser = PDFResumeParser()
    parsed = parser.parse_markdown(
        markdown="# Unknown Heading\njohn.doe@example.com\n+1 (415) 555-0100",
        source_file="resume.pdf",
    )

    assert parsed.section_items
    item = parsed.section_items[0]
    assert item.signals is not None
    assert "diagnostic_flags" in item.signals
    assert "confidence_inputs" in item.signals


def test_accented_and_markdown_headings_are_normalized() -> None:
    parser = PDFResumeParser()
    parsed = parser.parse_markdown(
        markdown="# **Educación**\nUBA\n# **Sobre mí**\nDocente y analista.",
        source_file="resume.pdf",
    )

    assert "education" in parsed.sections
    assert "summary" in parsed.sections
