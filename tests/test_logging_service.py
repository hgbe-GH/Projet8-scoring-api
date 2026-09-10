import json

from scoring_api.logging_service import PredictionEventLogger


def test_event_logger_writes_complete_success_event_to_file_and_stdout(
    tmp_path, capsys
) -> None:
    logger = PredictionEventLogger(tmp_path / "predictions.jsonl")

    logger.log_prediction(
        features={"heures_prevues": 21.0, "modalite": "standard"},
        risk_score=0.18,
        risk_flag=True,
        latency_ms=12.5,
        model_version="2026-06-15",
    )

    event = json.loads((tmp_path / "predictions.jsonl").read_text())
    output = capsys.readouterr().out

    assert event["schema_version"] == 1
    assert event["event_id"]
    assert event["timestamp"]
    assert event["event_type"] == "prediction"
    assert event["status"] == "success"
    assert event["http_status"] == 200
    assert event["features"]["heures_prevues"] == 21.0
    assert event["risk_score"] == 0.18
    assert event["latency_ms"] == 12.5
    assert output.startswith("ML_EVENT ")


def test_event_logger_writes_an_opaque_error_event(tmp_path) -> None:
    logger = PredictionEventLogger(tmp_path / "predictions.jsonl")

    logger.log_error(
        http_status=422,
        latency_ms=2.5,
        model_version="2026-06-15",
        error_code="validation_error",
    )

    event = json.loads((tmp_path / "predictions.jsonl").read_text())

    assert event["event_type"] == "prediction"
    assert event["status"] == "error"
    assert event["http_status"] == 422
    assert event["latency_ms"] == 2.5
    assert event["error_code"] == "validation_error"
    assert "features" not in event
    assert "error_detail" not in event
