import pytest
from pydantic import ValidationError

from scoring_api.schemas import PredictionRequest


def test_prediction_request_accepts_complete_payload(valid_payload: dict[str, object]) -> None:
    request = PredictionRequest.model_validate(valid_payload)

    assert request.client_effectif == valid_payload["client_effectif"]


def test_prediction_request_rejects_missing_required_feature(valid_payload: dict[str, object]) -> None:
    valid_payload.pop("heures_prevues")

    with pytest.raises(ValidationError, match="heures_prevues"):
        PredictionRequest.model_validate(valid_payload)


def test_prediction_request_rejects_text_for_numeric_feature(valid_payload: dict[str, object]) -> None:
    valid_payload["montant_demande_eur"] = "not-a-number"

    with pytest.raises(ValidationError, match="montant_demande_eur"):
        PredictionRequest.model_validate(valid_payload)


def test_prediction_request_rejects_negative_planned_hours(valid_payload: dict[str, object]) -> None:
    valid_payload["heures_prevues"] = -1.0

    with pytest.raises(ValidationError, match="heures_prevues"):
        PredictionRequest.model_validate(valid_payload)
