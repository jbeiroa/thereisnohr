from src.ingest.identity import (
    compute_identity_key,
    extract_emails,
    extract_identity,
    extract_phones,
)
from src.ingest.parser import PDFResumeParser


def test_extract_emails_normalizes_and_deduplicates() -> None:
    text = "Contact: mailto:John.Doe@example.com, john.doe@example.com."
    emails = extract_emails(text)

    assert emails == ["john.doe@example.com"]


def test_extract_phones_normalizes_mixed_formats() -> None:
    text = "Phone: +1 (415) 555-0100 | Alt: 415.555.0100"
    phones = extract_phones(text)

    assert "+14155550100" in phones
    assert "4155550100" in phones


def test_extract_identity_uses_email_name_alignment() -> None:
    parser = PDFResumeParser()
    parsed = parser.parse_markdown(
        markdown="# John Doe\njdoe@example.com\n+1 415 555 0100\n# Experience\nTeacher",
        source_file="resume.pdf",
    )

    identity = extract_identity(parsed)

    assert identity.name == "John Doe"
    assert identity.email == "jdoe@example.com"
    assert identity.phone == "+14155550100"
    assert identity.identity_key.startswith("candidate:v1:")
    assert identity.confidence > 0.7


def test_extract_identity_falls_back_to_content_hash_when_missing_signals() -> None:
    parser = PDFResumeParser()
    parsed = parser.parse_markdown(
        markdown="# Experience\nTaught physics and math",
        source_file="resume.pdf",
    )

    identity = extract_identity(parsed)

    assert identity.identity_key.startswith("resume_content:")
    assert identity.confidence <= 0.35


def test_identity_key_deterministic_for_same_identity_tuple() -> None:
    key_one, _ = compute_identity_key(
        name="John Doe",
        email="jdoe@example.com",
        phone="+14155550100",
        clean_text="ignored",
    )
    key_two, _ = compute_identity_key(
        name="john doe",
        email="JDOE@example.com",
        phone="+1 (415) 555-0100",
        clean_text="ignored",
    )

    assert key_one == key_two
