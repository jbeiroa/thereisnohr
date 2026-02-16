from dataclasses import dataclass
from pathlib import Path


@dataclass
class IngestionService:
    def ingest_resume(self, path: Path) -> str:
        if not path.exists():
            raise FileNotFoundError(f"Resume not found: {path}")
        return path.read_text(encoding="utf-8", errors="ignore")
