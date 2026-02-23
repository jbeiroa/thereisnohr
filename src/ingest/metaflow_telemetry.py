from __future__ import annotations

import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import mean
from time import perf_counter
from typing import Any

from metaflow import FlowMutator, current, user_step_decorator
from metaflow.cards import Markdown, Table, ValueBox


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _telemetry_enabled(flow: Any) -> bool:
    enabled = getattr(flow, "metrics_enabled", None)
    if isinstance(enabled, bool):
        return enabled
    return _parse_bool(os.getenv("INGEST_FLOW_METRICS_ENABLED"), default=True)


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return round(values[0], 4)

    values = sorted(values)
    position = max(0.0, min(1.0, p / 100.0)) * (len(values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower
    value = values[lower] * (1.0 - weight) + values[upper] * weight
    return round(value, 4)


def _collect_step_event(
    flow: Any,
    *,
    step_name: str,
    start_ts: str,
    end_ts: str,
    duration_ms: float,
    status: str,
    exception_type: str | None,
) -> None:
    event = {
        "step_name": step_name,
        "task_pathspec": getattr(current, "pathspec", None),
        "start_ts": start_ts,
        "end_ts": end_ts,
        "duration_ms": round(duration_ms, 3),
        "status": status,
        "exception_type": exception_type,
    }

    events = list(getattr(flow, "_step_telemetry_events", []))
    events.append(event)
    flow._step_telemetry_events = events
    flow._step_telemetry_event = event


def _ingest_step_telemetry_impl(step_name: str, flow: Any, inputs: Any, attributes: dict):
    if not _telemetry_enabled(flow):
        yield
        return

    started_at = _utc_now_iso()
    t0 = perf_counter()
    status = "success"
    exception_type: str | None = None

    try:
        yield
    except Exception as exc:
        status = "error"
        exception_type = exc.__class__.__name__
        raise
    finally:
        elapsed_ms = (perf_counter() - t0) * 1000
        _collect_step_event(
            flow,
            step_name=step_name,
            start_ts=started_at,
            end_ts=_utc_now_iso(),
            duration_ms=elapsed_ms,
            status=status,
            exception_type=exception_type,
        )


ingest_step_telemetry = user_step_decorator(_ingest_step_telemetry_impl)


class IngestionTelemetryMutator(FlowMutator):
    def init(self, exclude_steps: list[str] | None = None):
        self.exclude_steps = set(exclude_steps or [])

    def pre_mutate(self, mutable_flow):
        for step_name, mutable_step in mutable_flow.steps:
            if step_name in self.exclude_steps:
                continue
            mutable_step.add_decorator(ingest_step_telemetry, duplicates=mutable_step.IGNORE)


def summarize_status_counts(results: list[dict]) -> dict[str, int]:
    statuses = [result.get("status", "unknown") for result in results]
    counts = Counter(statuses)
    return dict(sorted(counts.items(), key=lambda item: item[0]))


def summarize_reason_breakdown(results: list[dict]) -> dict[str, dict[str, int]]:
    skip_reasons = Counter()
    error_types = Counter()

    for result in results:
        status = result.get("status")
        if status and status.startswith("skipped_"):
            skip_reasons[status] += 1
        if status == "error":
            error_type = result.get("error_type") or "UnknownError"
            error_types[error_type] += 1

    return {
        "skip_reasons": dict(skip_reasons),
        "error_types": dict(error_types),
    }


def summarize_step_timing(step_events: list[dict]) -> dict[str, dict[str, float | int | None]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    error_counts: dict[str, int] = defaultdict(int)

    for event in step_events:
        step_name = event.get("step_name") or "unknown"
        duration = event.get("duration_ms")
        if isinstance(duration, (int, float)):
            grouped[step_name].append(float(duration))
        if event.get("status") == "error":
            error_counts[step_name] += 1

    summary: dict[str, dict[str, float | int | None]] = {}
    for step_name, durations in grouped.items():
        summary[step_name] = {
            "count": len(durations),
            "error_count": error_counts.get(step_name, 0),
            "p50_ms": _percentile(durations, 50),
            "p95_ms": _percentile(durations, 95),
            "max_ms": round(max(durations), 4) if durations else None,
        }

    for step_name, error_count in error_counts.items():
        summary.setdefault(
            step_name,
            {
                "count": 0,
                "error_count": error_count,
                "p50_ms": None,
                "p95_ms": None,
                "max_ms": None,
            },
        )

    return dict(sorted(summary.items(), key=lambda item: item[0]))


def _summarize_numeric(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "mean": None,
            "min": None,
            "max": None,
            "p50": None,
            "p95": None,
        }

    return {
        "count": len(values),
        "mean": round(mean(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "p50": _percentile(values, 50),
        "p95": _percentile(values, 95),
    }


def summarize_confidence(results: list[dict]) -> dict[str, dict[str, float | int | None]]:
    identity_values = [
        float(value)
        for value in (result.get("identity_confidence") for result in results)
        if isinstance(value, (int, float))
    ]
    section_values = [
        float(value)
        for value in (result.get("avg_section_confidence") for result in results)
        if isinstance(value, (int, float))
    ]

    return {
        "identity_confidence": _summarize_numeric(identity_values),
        "avg_section_confidence": _summarize_numeric(section_values),
    }


def build_run_report(
    *,
    run_meta: dict,
    results: list[dict],
    step_events: list[dict],
    sample_limit: int = 100,
) -> dict:
    status_counts = summarize_status_counts(results)
    total_files = len(results)
    ingested = status_counts.get("ingested", 0)
    success_rate = round((ingested / total_files) * 100, 2) if total_files else 0.0

    return {
        "metrics_version": run_meta.get("metrics_version", "stage3.metrics.v1"),
        "run_meta": run_meta,
        "status_counts": status_counts,
        "step_timing_summary": summarize_step_timing(step_events),
        "ingest_quality": summarize_confidence(results),
        "reason_breakdown": summarize_reason_breakdown(results),
        "totals": {
            "files_total": total_files,
            "success_rate": success_rate,
        },
        "files": results,
        "files_sample": results[:sample_limit],
        "files_sample_truncated": max(0, total_files - sample_limit),
        "step_events": step_events,
    }


def _kpi_markup(report: dict) -> str:
    status = report.get("status_counts", {})
    total = report.get("totals", {}).get("files_total", 0)
    success = report.get("totals", {}).get("success_rate", 0.0)

    def tile(title: str, value: Any, color: str) -> str:
        return (
            "<div style='flex:1; min-width:140px; padding:12px; border-radius:12px;"
            " border:1px solid #dbe2ef; background:linear-gradient(135deg,#ffffff,#f6f9fc);'>"
            f"<div style='font-size:12px;color:#5f6c7b'>{title}</div>"
            f"<div style='font-size:24px;font-weight:700;color:{color}'>{value}</div>"
            "</div>"
        )

    tiles = [
        tile("Files", total, "#1f2937"),
        tile("Ingested", status.get("ingested", 0), "#0f766e"),
        tile("Skipped", status.get("skipped_existing_resume", 0) + status.get("skipped_existing_content", 0), "#a16207"),
        tile("Errors", status.get("error", 0), "#b91c1c"),
        tile("Success %", f"{success}%", "#1d4ed8"),
    ]

    return (
        "<div style='display:flex;flex-wrap:wrap;gap:10px;margin:8px 0 18px 0;'>"
        + "".join(tiles)
        + "</div>"
    )


def _build_status_table(report: dict) -> Table:
    status_counts = report.get("status_counts", {})
    rows = [[status, count] for status, count in sorted(status_counts.items())]
    return Table(data=rows or [["(none)", 0]], headers=["Status", "Count"])


def _build_confidence_table(report: dict) -> Table:
    quality = report.get("ingest_quality", {})
    rows: list[list[Any]] = []
    for metric_name, values in quality.items():
        rows.append(
            [
                metric_name,
                values.get("count"),
                values.get("mean"),
                values.get("p50"),
                values.get("p95"),
                values.get("max"),
            ]
        )
    return Table(
        data=rows or [["(none)", 0, None, None, None, None]],
        headers=["Metric", "Count", "Mean", "P50", "P95", "Max"],
    )


def _build_reason_table(report: dict) -> Table:
    reasons = report.get("reason_breakdown", {})
    rows: list[list[Any]] = []
    for status, count in sorted((reasons.get("skip_reasons") or {}).items()):
        rows.append(["skip", status, count])
    for err, count in sorted((reasons.get("error_types") or {}).items()):
        rows.append(["error", err, count])
    return Table(data=rows or [["(none)", "(none)", 0]], headers=["Type", "Reason", "Count"])


def _build_file_table(report: dict) -> Table:
    files = report.get("files_sample", [])
    rows: list[list[Any]] = []
    for item in files:
        rows.append(
            [
                item.get("status"),
                item.get("source_file"),
                item.get("duration_ms"),
                item.get("identity_confidence"),
                item.get("avg_section_confidence"),
                item.get("error_type"),
            ]
        )
    truncated = report.get("files_sample_truncated", 0)
    if truncated:
        rows.append(["...", f"{truncated} more rows", None, None, None, None])

    return Table(
        data=rows or [["(none)", "(none)", None, None, None, None]],
        headers=[
            "Status",
            "Source File",
            "Duration (ms)",
            "Identity Conf",
            "Section Conf",
            "Error Type",
        ],
    )


def render_run_report_card(report: dict) -> list[Any]:
    run_meta = report.get("run_meta", {})

    return [
        Markdown("# Resume Ingestion Run Metrics"),
        Markdown(
            f"**Run ID:** `{run_meta.get('run_id')}`  \\n"
            f"**Started:** `{run_meta.get('started_at')}`  \\n"
            f"**Finished:** `{run_meta.get('finished_at')}`  \\n"
            f"**Pattern:** `{run_meta.get('pattern')}`"
        ),
        Markdown(_kpi_markup(report)),
        ValueBox(title="Metrics Version", value=report.get("metrics_version", "unknown"), theme="light"),
        Markdown("## Status Breakdown"),
        _build_status_table(report),
        Markdown("## Confidence Summary"),
        _build_confidence_table(report),
        Markdown("## Top Skip/Error Reasons"),
        _build_reason_table(report),
        Markdown("## Per-file Outcomes (sample)"),
        _build_file_table(report),
    ]


def attach_run_report_card(report: dict, card_id: str = "run_metrics") -> bool:
    card_container = getattr(current, "card", None)
    if card_container is None:
        return False

    target = card_container
    try:
        target = card_container[card_id]
    except Exception:
        target = card_container

    components = render_run_report_card(report)
    for component in components:
        target.append(component)
    return True
