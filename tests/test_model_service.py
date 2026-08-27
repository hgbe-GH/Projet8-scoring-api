from pathlib import Path
import warnings

from sklearn.exceptions import InconsistentVersionWarning

from scoring_api.model_service import ModelService
from scoring_api.schemas import PredictionRequest


def test_model_service_scores_valid_request(valid_payload: dict[str, object]) -> None:
    root = Path(__file__).resolve().parents[1]
    service = ModelService.from_paths(
        root / "models/matchers_option_a_model.joblib",
        root / "models/matchers_option_a_metadata.json",
    )

    result = service.predict(PredictionRequest.model_validate(valid_payload))

    assert 0.0 <= result.risk_score <= 1.0
    assert result.threshold == 0.06
    assert result.model_name == "xgboost_search"


def test_model_service_loads_the_file_once(monkeypatch, valid_payload: dict[str, object]) -> None:
    root = Path(__file__).resolve().parents[1]
    calls = 0
    original_load = __import__("joblib").load

    def counted_load(path):
        nonlocal calls
        calls += 1
        return original_load(path)

    monkeypatch.setattr("scoring_api.model_service.joblib.load", counted_load)
    service = ModelService.from_paths(
        root / "models/matchers_option_a_model.joblib",
        root / "models/matchers_option_a_metadata.json",
    )
    request = PredictionRequest.model_validate(valid_payload)

    service.predict(request)
    service.predict(request)

    assert calls == 1


def test_model_service_uses_the_serialisation_compatible_sklearn_version() -> None:
    root = Path(__file__).resolve().parents[1]

    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")
        ModelService.from_paths(
            root / "models/matchers_option_a_model.joblib",
            root / "models/matchers_option_a_metadata.json",
        )

    assert not any(
        issubclass(warning.category, InconsistentVersionWarning)
        for warning in caught_warnings
    )
