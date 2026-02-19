from dataclasses import dataclass


@dataclass
class ExtractionService:
    def extract_sections(self, text: str) -> dict[str, str]:
        return {"raw": text}
