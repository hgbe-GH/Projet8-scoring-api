import pytest

from scoring_api.evidently_monitoring import build_evidently_report


def _events(count: int, hours: int) -> list[dict]:
    return [
        {
            "status": "success",
            "features": {
                "heures_prevues": hours + index,
                "montant_demande_eur": 1000 + index * 30,
                "pct_financement_demande": 0.5 + index / 100,
                "modalite": "standard",
                "source_lead": "direct",
                "type_financement": "classique",
            },
        }
        for index in range(count)
    ]


def test_evidently_report_runs_on_reference_and_production(tmp_path) -> None:
    result = build_evidently_report(_events(30, 10), _events(30, 100), tmp_path)

    assert result["status"] == "ok"
    assert result["reference_rows"] == 30
    assert result["production_rows"] == 30
    assert result["drifted_columns"] >= 1
    assert "heures_prevues" in result["columns"]
    assert result["columns"]["modalite"]["method"] == "jensenshannon"
    assert (tmp_path / "evidently_report.html").is_file()
    assert (tmp_path / "evidently_report.json").is_file()


def test_evidently_report_marks_small_samples_as_insufficient(tmp_path) -> None:
    (tmp_path / "evidently_report.html").write_text("stale", encoding="utf-8")
    (tmp_path / "evidently_report.json").write_text("stale", encoding="utf-8")
    result = build_evidently_report(_events(1, 10), _events(1, 100), tmp_path)

    assert result["status"] == "insufficient_data"
    assert result["drifted_columns"] is None
    assert not (tmp_path / "evidently_report.html").exists()
    assert not (tmp_path / "evidently_report.json").exists()
