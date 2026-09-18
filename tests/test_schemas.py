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


def test_prediction_request_accepts_training_boolean_types_and_missing_values(
    valid_payload: dict[str, object],
) -> None:
    for name in (
        "duree_sous_seuil_min", "est_nouvel_opco_pour_client",
        "is_premier_dossier", "is_rush_q4", "is_session_ete",
    ):
        valid_payload[name] = False
    for name in (
        "client_ape_division", "client_departement", "client_effectif",
        "client_opco_habituel", "client_prior_win_rate", "ape_division",
        "departement_client", "effectif_client", "jours_depuis_dernier_dossier",
        "modalite", "opco_habituel_client", "pct_financement_demande",
        "source_lead", "type_financement", "hg_departement_client",
        "hg_opco_entreprise", "hg_taille_entreprise",
    ):
        valid_payload[name] = None

    request = PredictionRequest.model_validate(valid_payload)

    assert request.is_rush_q4 is False
    assert request.source_lead is None
    assert request.client_effectif is None


def test_prediction_request_rejects_boolean_text(valid_payload: dict[str, object]) -> None:
    valid_payload["is_rush_q4"] = "false"

    with pytest.raises(ValidationError, match="is_rush_q4"):
        PredictionRequest.model_validate(valid_payload)


def test_prediction_request_accepts_zero_rank_and_amount_seen_in_holdout(
    valid_payload: dict[str, object],
) -> None:
    valid_payload["client_rang_dossier"] = 0
    valid_payload["montant_demande_eur"] = 0.0

    request = PredictionRequest.model_validate(valid_payload)

    assert request.client_rang_dossier == 0
    assert request.montant_demande_eur == 0.0
