"""Application module `src.ingest.pdf_ingestion_flow`."""

from datetime import datetime, timezone
from pathlib import Path

from metaflow import FlowSpec, Parameter, card, current, step

from src.core.config import get_settings
from src.ingest.metaflow_telemetry import (
    IngestionTelemetryMutator,
    attach_run_report_card,
    build_run_report,
)
from src.ingest.service import IngestionService
from src.storage.db import get_session


@IngestionTelemetryMutator()
class ResumePdfIngestionFlow(FlowSpec):
    """Represents ResumePdfIngestionFlow."""

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
        """Run start.

        """
        settings = get_settings()
        input_dir_path = Path(self.input_dir)
        if not input_dir_path.is_absolute():
            input_dir_path = (Path.cwd() / input_dir_path).resolve()

        self.metrics_enabled = settings.ingest_flow_metrics_enabled
        self.metrics_version = "stage3.metrics.v1"
        self.settings = {
            "database_url": settings.database_url,
            "input_dir": str(input_dir_path),
            "pattern": self.pattern,
        }
        self.run_meta = {
            "metrics_version": self.metrics_version,
            "run_id": getattr(current, "run_id", None),
            "flow_name": getattr(current, "flow_name", self.__class__.__name__),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "input_dir": str(input_dir_path),
            "pattern": self.pattern,
        }
        self.step_events = []
        self.next(self.discover_files)

    @step
    def discover_files(self):
        """Run discover files.

        """
        service = IngestionService()
        files = service.discover_pdf_files(Path(self.settings["input_dir"]), self.settings["pattern"])
        self.pdf_files = [str(path) for path in files]
        self.discovery_metrics = {
            "discovered_count": len(self.pdf_files),
            "input_dir": self.settings["input_dir"],
            "pattern": self.settings["pattern"],
        }

        if not self.pdf_files:
            self.results = []
            self.next(self.end)
            return

        self.next(self.ingest_one, foreach="pdf_files")

    @step
    def ingest_one(self):
        """Run ingest one.

        """
        file_path = Path(self.input)
        service = IngestionService()
        session = get_session()
        started = datetime.now(timezone.utc)

        try:
            result = service.ingest_pdf(file_path, session)
            session.commit()
            duration_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000.0
            self.ingest_result = {
                "status": result.status,
                "source_file": result.source_file,
                "candidate_id": result.candidate_id,
                "resume_id": result.resume_id,
                "section_count": result.section_count,
                "identity_confidence": result.identity_confidence,
                "avg_section_confidence": result.avg_section_confidence,
                "duration_ms": round(duration_ms, 3),
                "error_type": None,
            }
        except Exception as exc:
            session.rollback()
            duration_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000.0
            self.ingest_result = {
                "status": "error",
                "source_file": str(file_path),
                "error": str(exc),
                "error_type": exc.__class__.__name__,
                "duration_ms": round(duration_ms, 3),
                "identity_confidence": None,
                "avg_section_confidence": None,
            }
        finally:
            session.close()

        self.next(self.join_results)

    @step
    def join_results(self, inputs):
        """Run join results.

        Args:
            inputs: Input parameter.

        """
        self.results = [inp.ingest_result for inp in inputs]
        events: list[dict] = list(getattr(self, "_step_telemetry_events", []))
        for inp in inputs:
            events.extend(getattr(inp, "_step_telemetry_events", []))
        self.step_events = events
        self.next(self.end)

    @card(type="blank", id="run_metrics")
    @step
    def end(self):
        """Run end.

        """
        if not hasattr(self, "results"):
            self.results = []
        if not hasattr(self, "step_events"):
            self.step_events = list(getattr(self, "_step_telemetry_events", []))

        run_meta = dict(getattr(self, "run_meta", {}))
        run_meta["finished_at"] = datetime.now(timezone.utc).isoformat()
        run_meta["metrics_enabled"] = bool(getattr(self, "metrics_enabled", True))
        run_meta["discovery"] = getattr(self, "discovery_metrics", {})

        self.run_report = build_run_report(
            run_meta=run_meta,
            results=self.results,
            step_events=self.step_events,
            sample_limit=100,
        )

        card_attached = False
        if getattr(self, "metrics_enabled", True):
            card_attached = attach_run_report_card(self.run_report, card_id="run_metrics")

        status_counts = self.run_report.get("status_counts", {})
        ingested = status_counts.get("ingested", 0)
        skipped = (
            status_counts.get("skipped_existing_resume", 0)
            + status_counts.get("skipped_existing_content", 0)
        )
        errors = status_counts.get("error", 0)
        print(
            "Resume ingestion completed: "
            f"ingested={ingested}, skipped={skipped}, errors={errors}, "
            f"card_attached={card_attached}"
        )


if __name__ == "__main__":
    ResumePdfIngestionFlow()
