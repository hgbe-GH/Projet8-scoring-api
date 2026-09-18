"""Analyze locally stored monitoring events and write JSON and Markdown reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from scoring_api.evidently_monitoring import build_evidently_report
from scoring_api.monitoring_analysis import build_monitoring_report
from scoring_api.monitoring_config import DATABASE_PATH, REFERENCE_PATH, REPORT_DIR
from scoring_api.monitoring_storage import list_prediction_events, storage_evidence


def parse_arguments() -> argparse.Namespace:
    """Return parameters for the local monitoring analysis."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database", type=Path, default=DATABASE_PATH
    )
    parser.add_argument("--reference", type=Path, default=REFERENCE_PATH)
    parser.add_argument(
        "--output-dir", type=Path, default=REPORT_DIR
    )
    return parser.parse_args()


def load_reference_events(path: Path) -> list[dict[str, Any]]:
    """Load a reference with a declared, consistent provenance."""
    events = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    source = events[0].get("reference_source") if events and isinstance(events[0], dict) else None
    if not isinstance(source, str) or not source.strip() or any(
        not isinstance(event, dict) or event.get("reference_source") != source
        for event in events
    ):
        raise ValueError("Reference events need one non-empty reference_source")
    return events


def markdown_report(report: dict[str, Any]) -> str:
    """Render a concise human-readable companion to the JSON report."""
    operational = report["operational"]
    drift = report["drift"]
    lines = [
        "# Monitoring report",
        "",
        f"Generated at: {report['generated_at']}",
        f"Reference source: {report['reference_source']}",
        "",
        "## Operational metrics",
        "",
        f"- Events: {operational['total_events']}",
        f"- Error rate: {operational['error_rate']:.2%} (alert: {operational['error_rate_alert']})",
        f"- Median latency: {operational['median_latency_ms']}",
        f"- P95 latency: {operational['p95_latency_ms']} (alert: {operational['p95_latency_alert']})",
        "",
        "## Drift",
        "",
        f"- Successful reference events: {drift['reference_successful_events']}",
        f"- Successful production events: {drift['production_successful_events']}",
        "",
        "## SQLite storage evidence",
        "",
        f"- Stored rows: {report['storage']['row_count']}",
        f"- Successful rows: {report['storage']['successful_count']}",
        f"- First timestamp: {report['storage']['earliest_timestamp']}",
        f"- Last timestamp: {report['storage']['latest_timestamp']}",
        f"- Last event ID: {report['storage']['latest_event_id']}",
        "",
        "## Evidently AI",
        "",
        f"- Status: {report['evidently']['status']}",
        f"- Drifted columns: {report['evidently']['drifted_columns']}",
        f"- Drifted share: {report['evidently']['drifted_share']}",
    ]
    lines.extend(_metric_lines("PSI", drift["numeric"], "psi"))
    lines.extend(
        _metric_lines(
            "Unknown category rate",
            drift["categorical"],
            "unknown_category_rate",
        )
    )
    if report["reference_source"] == "synthetic_demo":
        lines.extend(
            [
                "",
                "Synthetic reference: demonstration only; not a production drift conclusion.",
            ]
        )
    return "\n".join(lines) + "\n"


def _metric_lines(
    title: str, metrics: dict[str, dict[str, Any]], value_key: str
) -> list[str]:
    lines = ["", f"### {title}", ""]
    for feature, metric in metrics.items():
        lines.append(
            f"- {feature}: {metric[value_key]} (status: {metric['status']}, alert: {metric['alert']})"
        )
    return lines


def main() -> int:
    """Load monitoring inputs and write report files."""
    arguments = parse_arguments()
    if not arguments.database.is_file() or not arguments.reference.is_file():
        print("Database and reference files must exist.", file=sys.stderr)
        return 2

    try:
        reference_events = load_reference_events(arguments.reference)
        production_events = list_prediction_events(arguments.database)
        report = build_monitoring_report(reference_events, production_events)
        report["storage"] = storage_evidence(arguments.database)
        report["evidently"] = build_evidently_report(
            reference_events, production_events, arguments.output_dir
        )
    except ValueError as error:
        print(f"Analysis failed: {error}", file=sys.stderr)
        return 2
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    (arguments.output_dir / "latest_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (arguments.output_dir / "latest_report.md").write_text(
        markdown_report(report), encoding="utf-8"
    )
    print(f"Monitoring report written to {arguments.output_dir}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
