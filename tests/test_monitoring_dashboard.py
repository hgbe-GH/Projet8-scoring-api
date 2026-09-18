import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from scripts.generate_monitoring_demo import generate_demo
from scoring_api.monitoring_storage import import_render_export, storage_evidence


def test_dashboard_displays_report_and_sqlite_evidence(tmp_path, monkeypatch) -> None:
    reference, export = generate_demo(tmp_path)
    database = tmp_path / "monitoring.db"
    import_render_export(export, database)
    report = {
        "generated_at": "2026-09-17T12:00:00+00:00",
        "reference_source": "synthetic_demo",
        "operational": {
            "total_events": 30, "error_count": 0, "error_rate": 0.0,
            "median_latency_ms": 25.0, "p95_latency_ms": 25.0,
        },
        "drift": {
            "reference_successful_events": 30,
            "production_successful_events": 30,
            "numeric": {"heures_prevues": {"status": "ok", "psi": 2.1, "alert": True}},
            "categorical": {"modalite": {"status": "ok", "unknown_category_rate": 0.5, "alert": True}},
        },
        "evidently": {
            "status": "ok", "drifted_columns": 2, "drifted_share": 0.33,
            "reference_rows": 30, "production_rows": 30,
            "columns": {"heures_prevues": {
                "method": "K-S p_value", "score": 0.001,
                "threshold": 0.05, "drift_detected": True,
            }},
        },
        "storage": storage_evidence(database),
    }
    report_path = tmp_path / "latest_report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setenv("MONITORING_REPORT_PATH", str(report_path))
    monkeypatch.setenv("MONITORING_DATABASE_PATH", str(database))

    app = AppTest.from_file(
        Path(__file__).parents[1] / "scripts/monitoring_dashboard.py"
    ).run()

    assert not app.exception
    assert any("Monitoring" in item.value for item in app.title)
    assert any("30" in str(item.value) for item in app.metric)
    assert not any("Relancez l'analyse" in item.value for item in app.warning)

    report["storage"]["row_count"] = 29
    report_path.write_text(json.dumps(report), encoding="utf-8")
    stale_app = AppTest.from_file(
        Path(__file__).parents[1] / "scripts/monitoring_dashboard.py"
    ).run()
    assert any("Relancez l'analyse" in item.value for item in stale_app.warning)
