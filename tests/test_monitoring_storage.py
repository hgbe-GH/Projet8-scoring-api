import json

import pytest

from scoring_api.monitoring_storage import import_render_export, list_prediction_events


def success_event(event_id: str = "event-1") -> dict[str, object]:
    return {
        "schema_version": 1,
        "event_id": event_id,
        "timestamp": "2026-09-10T12:00:00+00:00",
        "event_type": "prediction",
        "status": "success",
        "http_status": 200,
        "latency_ms": 12.5,
        "model_version": "2026-06-15",
        "features": {"heures_prevues": 21.0, "modalite": "standard"},
        "risk_score": 0.18,
        "risk_flag": True,
    }


def test_import_render_export_stores_only_ml_events_once(tmp_path) -> None:
    export = tmp_path / "render-export.jsonl"
    export.write_text(
        json.dumps({"message": "unrelated Render message"})
        + "\n"
        + json.dumps({"message": "ML_EVENT " + json.dumps(success_event())})
        + "\n",
        encoding="utf-8",
    )
    database = tmp_path / "monitoring.db"

    assert import_render_export(export, database) == 1
    assert import_render_export(export, database) == 0

    events = list_prediction_events(database)
    assert len(events) == 1
    assert events[0]["event_id"] == "event-1"
    assert events[0]["features"] == {
        "heures_prevues": 21.0,
        "modalite": "standard",
    }


def test_import_render_export_reads_concatenated_pretty_json_objects(tmp_path) -> None:
    export = tmp_path / "render-export.json"
    first = {"message": "ML_EVENT " + json.dumps(success_event("event-1"))}
    second = {"message": "ML_EVENT " + json.dumps(success_event("event-2"))}
    export.write_text(
        json.dumps(first, indent=2) + json.dumps(second, indent=2), encoding="utf-8"
    )

    imported = import_render_export(export, tmp_path / "monitoring.db")

    assert imported == 2


def test_import_render_export_rejects_malformed_monitoring_event(tmp_path) -> None:
    export = tmp_path / "render-export.jsonl"
    export.write_text(
        json.dumps({"message": "ML_EVENT {not-json}"}), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="Malformed ML_EVENT payload"):
        import_render_export(export, tmp_path / "monitoring.db")
