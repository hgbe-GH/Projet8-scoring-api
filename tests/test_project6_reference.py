"""A Projet6 monitoring reference must preserve provenance without raw records."""

import pandas as pd
import pytest

from scripts.build_project6_reference import build_reference_events


FEATURES = {
    "heures_prevues": 20.0,
    "montant_demande_eur": 2000.0,
    "pct_financement_demande": 0.8,
    "modalite": "standard",
    "source_lead": "direct",
    "type_financement": "classique",
}


def sample_frame() -> pd.DataFrame:
    rows = []
    for index, date in enumerate(
        ["2023-01-01", "2023-02-01", "2023-03-01", "2023-04-01", "2026-01-01"]
    ):
        rows.append(
            {
                "funding_id": f"private-{index}",
                "date_gagne": pd.Timestamp(date),
                "completion_failure_bin": index % 2,
                "statut_formation_normalized": "termine",
                "label_review_flag": False,
                **{**FEATURES, "heures_prevues": float(20 + index)},
            }
        )
    return pd.DataFrame(rows)


def sample_metadata() -> dict:
    return {
        "snapshot_date": "2026-06-15",
        "censor_days": 480,
        "test_fraction": 0.5,
        "terminal_statuses_used": ["termine", "annule", "en_cloture"],
        "exclude_label_review": True,
        "train_rows": 2,
        "holdout_rows": 2,
    }


def test_reference_uses_temporal_holdout_without_identifiers_or_labels() -> None:
    events = build_reference_events(sample_frame(), sample_metadata())

    assert len(events) == 2
    assert [event["features"]["heures_prevues"] for event in events] == [22.0, 23.0]
    assert {event["reference_source"] for event in events} == {
        "project6_temporal_holdout_2026-06-15"
    }
    assert all(set(event) == {"reference_source", "status", "features"} for event in events)
    assert all(set(event["features"]) == set(FEATURES) for event in events)


def test_reference_rejects_a_changed_training_population() -> None:
    metadata = sample_metadata()
    metadata["holdout_rows"] = 3

    with pytest.raises(ValueError, match="metadata row counts"):
        build_reference_events(sample_frame(), metadata)


def test_reference_rejects_incomplete_holdout_rows() -> None:
    frame = sample_frame()
    frame.loc[3, "source_lead"] = None

    with pytest.raises(ValueError, match="incomplete monitored features"):
        build_reference_events(frame, sample_metadata())
