"""Application module `src.extract.service`."""

from dataclasses import dataclass


@dataclass
class ExtractionService:
    """Represents ExtractionService."""

    def extract_sections(self, text: str) -> dict[str, str]:
        """Extract sections.

        Args:
            text: Input parameter.

        Returns:
            object: Computed result.

        """
        return {"raw": text}
