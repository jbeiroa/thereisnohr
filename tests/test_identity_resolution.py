from src.ingest.identity import (
    ModelNameResolver,
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


def test_extract_phones_rejects_short_date_like_numbers() -> None:
    text = "Date-like: 20032008"
    phones = extract_phones(text)
    assert phones == []


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
    assert identity.identity_key.startswith("candidate:v2:email:")
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
    assert key_one.startswith("candidate:v2:email:")


def test_identity_key_is_stable_when_phone_or_name_change_if_email_matches() -> None:
    key_one, _ = compute_identity_key(
        name="John Doe",
        email="jdoe@example.com",
        phone="+14155550100",
        clean_text="ignored",
    )
    key_two, _ = compute_identity_key(
        name="John X Doe",
        email="jdoe@example.com",
        phone="+14155550999",
        clean_text="ignored",
    )
    assert key_one == key_two


class _FakeModelResolver(ModelNameResolver):
    def resolve_name(self, text: str, context: dict) -> tuple[str | None, float, dict]:
        return "Juan Ignacio Beiroa", 0.9, {"method": "fake_model"}


def test_extract_identity_uses_model_fallback_when_rule_confidence_low() -> None:
    parser = PDFResumeParser()
    parsed = parser.parse_markdown(
        markdown="# Data Models\njbeiroa@gmail.com\n+54 9 11 3194-9050",
        source_file="resume.pdf",
    )

    identity = extract_identity(
        parsed,
        allow_model_fallback=True,
        model_name_resolver=_FakeModelResolver(),
    )
    assert identity.name == "Juan Ignacio Beiroa"
    assert identity.signals["model_fallback_used"] is True
