from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedResume:
    source_file: str
    raw_text: str
    clean_text: str
    links: list[str]
    sections: dict[str, str]
    language: str
    parser_version: str
