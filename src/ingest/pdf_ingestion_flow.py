from pathlib import Path

from metaflow import FlowSpec, Parameter, step

from src.core.config import get_settings
from src.ingest.service import IngestionService
from src.storage.db import get_session


class ResumePdfIngestionFlow(FlowSpec):
    input_dir = Parameter(
        "input-dir",
        help="Directory containing PDF resumes.",
        default="data",
    )
    pattern = Parameter(
        "pattern",
        help="Glob pattern for resumes.",
        default="*.pdf",
    )

    @step
    def start(self):
        settings = get_settings()
        input_dir_path = Path(self.input_dir)
        if not input_dir_path.is_absolute():
            input_dir_path = (Path.cwd() / input_dir_path).resolve()

        self.settings = {
            "database_url": settings.database_url,
            "input_dir": str(input_dir_path),
            "pattern": self.pattern,
        }
        self.next(self.discover_files)

    @step
    def discover_files(self):
        service = IngestionService()
        files = service.discover_pdf_files(Path(self.settings["input_dir"]), self.settings["pattern"])
        self.pdf_files = [str(path) for path in files]

        if not self.pdf_files:
            self.results = []
            self.next(self.end)
            return

        self.next(self.ingest_one, foreach="pdf_files")

    @step
    def ingest_one(self):
        file_path = Path(self.input)
        service = IngestionService()
        session = get_session()

        try:
            result = service.ingest_pdf(file_path, session)
            session.commit()
            self.ingest_result = {
                "status": result.status,
                "source_file": result.source_file,
                "candidate_id": result.candidate_id,
                "resume_id": result.resume_id,
                "section_count": result.section_count,
            }
        except Exception as exc:
            session.rollback()
            self.ingest_result = {
                "status": "error",
                "source_file": str(file_path),
                "error": str(exc),
            }
        finally:
            session.close()

        self.next(self.join_results)

    @step
    def join_results(self, inputs):
        self.results = [inp.ingest_result for inp in inputs]
        self.next(self.end)

    @step
    def end(self):
        if not hasattr(self, "results"):
            self.results = []
        ingested = sum(1 for result in self.results if result.get("status") == "ingested")
        skipped = sum(
            1
            for result in self.results
            if result.get("status") in {"skipped_existing_resume", "skipped_existing_content"}
        )
        errors = sum(1 for result in self.results if result.get("status") == "error")

        print(f"Resume ingestion completed: ingested={ingested}, skipped={skipped}, errors={errors}")


if __name__ == "__main__":
    ResumePdfIngestionFlow()
