import json

from fastapi.testclient import TestClient

from scoring_api import main
from scoring_api.main import app


def _latest_event(log_path) -> dict[str, object]:
    return json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])


def test_health_reports_ready_model() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["model_name"] == "xgboost_search"


def test_predict_returns_business_decision(valid_payload: dict[str, object]) -> None:
    with TestClient(app) as client:
        response = client.post("/predict", json=valid_payload)

    assert response.status_code == 200
    body = response.json()
    assert 0.0 <= body["risk_score"] <= 1.0
    assert body["threshold"] == 0.06
    assert body["risk_flag"] is (body["risk_score"] >= body["threshold"])


def test_predict_accepts_nulls_seen_during_training(valid_payload: dict[str, object]) -> None:
    for name in (
        "client_ape_division", "client_departement", "client_effectif",
        "client_opco_habituel", "client_prior_win_rate", "ape_division",
        "departement_client", "effectif_client", "jours_depuis_dernier_dossier",
        "modalite", "opco_habituel_client", "pct_financement_demande",
        "source_lead", "type_financement", "hg_departement_client",
        "hg_opco_entreprise", "hg_taille_entreprise",
    ):
        valid_payload[name] = None

    with TestClient(app) as client:
        response = client.post("/predict", json=valid_payload)

    assert response.status_code == 200
    assert 0 <= response.json()["risk_score"] <= 1


def test_predict_rejects_incomplete_payload(valid_payload: dict[str, object]) -> None:
    valid_payload.pop("funder_nom")

    with TestClient(app) as client:
        response = client.post("/predict", json=valid_payload)

    assert response.status_code == 422


def test_predict_logs_an_opaque_validation_error(
    valid_payload: dict[str, object], tmp_path, monkeypatch
) -> None:
    log_path = tmp_path / "predictions.jsonl"
    monkeypatch.setattr(main, "LOG_PATH", log_path)
    valid_payload.pop("funder_nom")

    with TestClient(app) as client:
        response = client.post("/predict", json=valid_payload)

    event = _latest_event(log_path)
    assert response.status_code == 422
    assert event["http_status"] == 422
    assert event["error_code"] == "validation_error"
    assert "features" not in event
    assert "error_detail" not in event


def test_predict_logs_an_opaque_prediction_error(
    valid_payload: dict[str, object], tmp_path, monkeypatch
) -> None:
    log_path = tmp_path / "predictions.jsonl"
    monkeypatch.setattr(main, "LOG_PATH", log_path)

    with TestClient(app) as client:
        service = app.state.model_service
        assert service is not None

        def fail_prediction(*_args, **_kwargs):
            raise RuntimeError("sensitive internal failure")

        monkeypatch.setattr(service, "predict", fail_prediction)
        response = client.post("/predict", json=valid_payload)

    event = _latest_event(log_path)
    assert response.status_code == 500
    assert event["http_status"] == 500
    assert event["error_code"] == "prediction_failed"
    assert "features" not in event
    assert "error_detail" not in event
