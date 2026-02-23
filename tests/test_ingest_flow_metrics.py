from src.ingest.metaflow_telemetry import (
    IngestionTelemetryMutator,
    _ingest_step_telemetry_impl,
    build_run_report,
    summarize_reason_breakdown,
    summarize_status_counts,
    summarize_step_timing,
)


def test_summarize_status_counts_and_reasons() -> None:
    results = [
        {"status": "ingested"},
        {"status": "skipped_existing_resume"},
        {"status": "skipped_existing_content"},
        {"status": "error", "error_type": "RuntimeError"},
        {"status": "error", "error_type": "ValueError"},
    ]

    counts = summarize_status_counts(results)
    reasons = summarize_reason_breakdown(results)

    assert counts["ingested"] == 1
    assert counts["skipped_existing_resume"] == 1
    assert counts["skipped_existing_content"] == 1
    assert counts["error"] == 2

    assert reasons["skip_reasons"]["skipped_existing_resume"] == 1
    assert reasons["skip_reasons"]["skipped_existing_content"] == 1
    assert reasons["error_types"]["RuntimeError"] == 1
    assert reasons["error_types"]["ValueError"] == 1


def test_summarize_step_timing_percentiles() -> None:
    events = [
        {"step_name": "ingest_one", "duration_ms": 10.0, "status": "success"},
        {"step_name": "ingest_one", "duration_ms": 20.0, "status": "success"},
        {"step_name": "ingest_one", "duration_ms": 30.0, "status": "error"},
        {"step_name": "discover_files", "duration_ms": 5.0, "status": "success"},
    ]

    summary = summarize_step_timing(events)

    assert summary["ingest_one"]["count"] == 3
    assert summary["ingest_one"]["error_count"] == 1
    assert summary["ingest_one"]["max_ms"] == 30.0
    assert summary["discover_files"]["count"] == 1


def test_build_run_report_contains_expected_keys() -> None:
    report = build_run_report(
        run_meta={"run_id": "123", "metrics_version": "stage3.metrics.v1"},
        results=[
            {
                "status": "ingested",
                "source_file": "a.pdf",
                "identity_confidence": 0.9,
                "avg_section_confidence": 0.8,
                "duration_ms": 12.0,
            },
            {
                "status": "skipped_existing_content",
                "source_file": "b.pdf",
                "identity_confidence": None,
                "avg_section_confidence": None,
                "duration_ms": 1.2,
            },
            {
                "status": "error",
                "source_file": "c.pdf",
                "error_type": "RuntimeError",
                "duration_ms": 5.1,
            },
        ],
        step_events=[{"step_name": "ingest_one", "duration_ms": 10.0, "status": "success"}],
    )

    assert set(report.keys()) >= {
        "run_meta",
        "status_counts",
        "step_timing_summary",
        "ingest_quality",
        "reason_breakdown",
        "files",
    }
    assert report["status_counts"]["ingested"] == 1
    assert report["status_counts"]["skipped_existing_content"] == 1
    assert report["status_counts"]["error"] == 1


def test_step_telemetry_impl_records_success_and_error() -> None:
    class Flow:
        metrics_enabled = True

    flow = Flow()

    success_gen = _ingest_step_telemetry_impl("start", flow, None, {})
    next(success_gen)
    try:
        success_gen.send(None)
    except StopIteration:
        pass

    assert flow._step_telemetry_event["step_name"] == "start"
    assert flow._step_telemetry_event["status"] == "success"

    error_gen = _ingest_step_telemetry_impl("ingest_one", flow, None, {})
    next(error_gen)
    try:
        error_gen.throw(ValueError("boom"))
    except ValueError:
        pass

    assert flow._step_telemetry_event["step_name"] == "ingest_one"
    assert flow._step_telemetry_event["status"] == "error"
    assert flow._step_telemetry_event["exception_type"] == "ValueError"


def test_mutator_applies_decorator_to_all_steps_except_excluded() -> None:
    class FakeStep:
        IGNORE = 1

        def __init__(self):
            self.decorators = []

        def add_decorator(self, deco_type, duplicates):
            self.decorators.append((deco_type, duplicates))

    class FakeMutableFlow:
        def __init__(self):
            self._steps = {
                "start": FakeStep(),
                "discover_files": FakeStep(),
                "end": FakeStep(),
            }

        @property
        def steps(self):
            return list(self._steps.items())

    mutator = IngestionTelemetryMutator()
    mutator.init(exclude_steps=["end"])

    flow = FakeMutableFlow()
    mutator.pre_mutate(flow)

    assert flow._steps["start"].decorators
    assert flow._steps["discover_files"].decorators
    assert flow._steps["end"].decorators == []
