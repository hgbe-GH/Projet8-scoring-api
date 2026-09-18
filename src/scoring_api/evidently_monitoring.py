"""Run Evidently on validated successful prediction inputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from evidently import DataDefinition, Dataset, Report
from evidently.presets import DataDriftPreset

from scoring_api.monitoring_config import (
    CATEGORICAL_DRIFT_FEATURES,
    EVIDENTLY_CATEGORICAL_METHOD,
    EVIDENTLY_CATEGORICAL_THRESHOLD,
    MINIMUM_DRIFT_SAMPLE_SIZE,
    NUMERIC_DRIFT_FEATURES,
)

FEATURES = NUMERIC_DRIFT_FEATURES + CATEGORICAL_DRIFT_FEATURES


def _feature_frame(events: list[dict[str, Any]]) -> pd.DataFrame:
    """Keep complete, typed feature rows from successful predictions."""
    rows = [
        event["features"]
        for event in events
        if event.get("status") == "success"
        and isinstance(event.get("features"), dict)
    ]
    frame = pd.DataFrame(rows).reindex(columns=FEATURES)
    for feature in NUMERIC_DRIFT_FEATURES:
        frame[feature] = pd.to_numeric(frame[feature], errors="coerce")
    for feature in CATEGORICAL_DRIFT_FEATURES:
        valid_values = frame[feature].map(lambda value: isinstance(value, str))
        frame[feature] = frame[feature].where(valid_values)
    return frame.dropna(subset=FEATURES).reset_index(drop=True)


def build_evidently_report(
    reference_events: list[dict[str, Any]],
    production_events: list[dict[str, Any]],
    output_dir: Path,
) -> dict[str, Any]:
    """Export Evidently artifacts and return a compact summary for the dashboard."""
    reference = _feature_frame(reference_events)
    production = _feature_frame(production_events)
    summary: dict[str, Any] = {
        "status": "insufficient_data",
        "reference_rows": len(reference),
        "production_rows": len(production),
        "drifted_columns": None,
        "drifted_share": None,
        "columns": {},
    }
    if min(len(reference), len(production)) < MINIMUM_DRIFT_SAMPLE_SIZE:
        for name in ("evidently_report.html", "evidently_report.json"):
            (output_dir / name).unlink(missing_ok=True)
        return summary

    definition = DataDefinition(
        numerical_columns=list(NUMERIC_DRIFT_FEATURES),
        categorical_columns=list(CATEGORICAL_DRIFT_FEATURES),
    )
    result = Report([
        DataDriftPreset(
            cat_method=EVIDENTLY_CATEGORICAL_METHOD,
            cat_threshold=EVIDENTLY_CATEGORICAL_THRESHOLD,
        )
    ]).run(
        Dataset.from_pandas(production, data_definition=definition),
        Dataset.from_pandas(reference, data_definition=definition),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    result.save_html(str(output_dir / "evidently_report.html"))
    result.save_json(str(output_dir / "evidently_report.json"))

    summary["status"] = "ok"
    for metric in result.dict()["metrics"]:
        config = metric["config"]
        if config["type"].endswith(":DriftedColumnsCount"):
            summary["drifted_columns"] = int(metric["value"]["count"])
            summary["drifted_share"] = float(metric["value"]["share"])
        elif config["type"].endswith(":ValueDrift"):
            method = config["method"]
            value = float(metric["value"])
            threshold = float(config["threshold"])
            summary["columns"][config["column"]] = {
                "method": method,
                "score": value,
                "threshold": threshold,
                "drift_detected": (
                    value <= threshold if "p_value" in method else value >= threshold
                ),
            }
    return summary
