from fastapi.testclient import TestClient

from scoring_api.main import app


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


def test_predict_rejects_incomplete_payload(valid_payload: dict[str, object]) -> None:
    valid_payload.pop("funder_nom")

    with TestClient(app) as client:
        response = client.post("/predict", json=valid_payload)

    assert response.status_code == 422
