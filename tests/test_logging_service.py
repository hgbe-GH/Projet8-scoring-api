import json

from scoring_api.logging_service import PredictionEventLogger


def test_event_logger_writes_features_score_and_latency(tmp_path) -> None:
    logger = PredictionEventLogger(tmp_path / "predictions.jsonl")

    logger.log_prediction(
        features={"heures_prevues": 21.0, "modalite": "standard"},
        risk_score=0.18,
        risk_flag=True,
        duration_ms=12.5,
        model_version="2026-06-15",
    )

    event = json.loads((tmp_path / "predictions.jsonl").read_text())

    assert event["event_type"] == "prediction"
    assert event["features"]["heures_prevues"] == 21.0
    assert event["risk_score"] == 0.18
    assert event["duration_ms"] == 12.5


def test_event_logger_writes_an_opaque_error_event(tmp_path) -> None:
    logger = PredictionEventLogger(tmp_path / "predictions.jsonl")

    logger.log_error(duration_ms=2.5, model_version="2026-06-15")

    event = json.loads((tmp_path / "predictions.jsonl").read_text())

    assert event["event_type"] == "prediction"
    assert event["status"] == "error"
    assert event["duration_ms"] == 2.5
    assert "error_detail" not in event
