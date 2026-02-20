from dataclasses import dataclass


@dataclass
class HeadingSpan:
    raw_heading: str
    title: str
    start_line: int
    end_line: int


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
    sections: dict[str, str]
    section_items: list[SectionItem]
    language: str
    parser_version: str
