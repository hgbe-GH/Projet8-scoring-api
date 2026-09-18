"""Build a private monitoring reference from the Projet6 temporal holdout."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any

import pandas as pd

from scoring_api.monitoring_config import (
    CATEGORICAL_DRIFT_FEATURES,
    NUMERIC_DRIFT_FEATURES,
)

MONITORED_FEATURES = NUMERIC_DRIFT_FEATURES + CATEGORICAL_DRIFT_FEATURES
REQUIRED_COLUMNS = {
    "funding_id",
    "date_gagne",
    "completion_failure_bin",
    "statut_formation_normalized",
    "label_review_flag",
    *MONITORED_FEATURES,
}


def build_reference_events(
    frame: pd.DataFrame, metadata: dict[str, Any]
) -> list[dict[str, Any]]:
    """Repeat the saved training split and retain only six monitored inputs."""
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(f"Modeling base misses required columns: {sorted(missing)}")

    snapshot = pd.Timestamp(metadata["snapshot_date"])
    dates = pd.to_datetime(frame["date_gagne"], errors="coerce")
    eligible = frame["completion_failure_bin"].notna() & dates.notna()
    eligible &= (snapshot - dates).dt.days >= int(metadata["censor_days"])
    eligible &= frame["statut_formation_normalized"].isin(
        metadata["terminal_statuses_used"]
    )
    if metadata["exclude_label_review"]:
        eligible &= ~frame["label_review_flag"].fillna(False).astype(bool)

    filtered = frame.loc[eligible].sort_values(
        ["date_gagne", "funding_id"]
    ).reset_index(drop=True)
    holdout_size = max(1, round(len(filtered) * float(metadata["test_fraction"])))
    if (
        len(filtered) - holdout_size != int(metadata["train_rows"])
        or holdout_size != int(metadata["holdout_rows"])
    ):
        raise ValueError("Projet6 modeling base does not match metadata row counts")

    holdout = filtered.iloc[-holdout_size:]
    if not holdout.loc[:, MONITORED_FEATURES].notna().all(axis=1).all():
        raise ValueError("Projet6 holdout has incomplete monitored features")

    source = f"project6_temporal_holdout_{snapshot.date().isoformat()}"
    events = []
    for _, row in holdout.iterrows():
        features: dict[str, float | str] = {}
        for feature in NUMERIC_DRIFT_FEATURES:
            value = float(row[feature])
            if not math.isfinite(value):
                raise ValueError(f"Non-finite monitored feature: {feature}")
            features[feature] = value
        for feature in CATEGORICAL_DRIFT_FEATURES:
            value = row[feature]
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Invalid monitored category: {feature}")
            features[feature] = value.strip()
        events.append(
            {"reference_source": source, "status": "success", "features": features}
        )
    return events


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modeling-base", type=Path, required=True)
    parser.add_argument(
        "--metadata", type=Path, default=Path("models/matchers_option_a_metadata.json")
    )
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    frame = pd.read_parquet(arguments.modeling_base)
    metadata = json.loads(arguments.metadata.read_text(encoding="utf-8"))
    events = build_reference_events(frame, metadata)
    arguments.output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(
        arguments.output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600
    )
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as destination:
        for event in events:
            destination.write(json.dumps(event, ensure_ascii=False) + "\n")
    print(
        f"Wrote {len(events)} Projet6 holdout reference rows to {arguments.output}. "
        "No identifiers or labels were exported."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
