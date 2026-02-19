from dataclasses import dataclass

@dataclass(frozen=True)
class SectionItem:
    raw_heading: str
    normalized_type: str
    content: str
    confidence: float
    signals: dict | None
@dataclass(frozen=True)
class IdentitySignals:
    name: str
    emails: str | list[str]
    phones: str | list[str]
    links: list[str]
@dataclass(frozen=True)
class ParsedResume:
    source_file: str
    raw_text: str
    clean_text: str
    links: list[str]
    section_items: list[SectionItem]
    identity_signals: IdentitySignals | None
    language: str
    parser_version: str
    content_hash: str | None
