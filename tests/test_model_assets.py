import json
from pathlib import Path


def test_model_metadata_describes_serialised_champion() -> None:
    root = Path(__file__).resolve().parents[1]
    metadata = json.loads((root / "models/matchers_option_a_metadata.json").read_text())

    assert (root / "models/matchers_option_a_model.joblib").is_file()
    assert metadata["champion_name"] == "xgboost_search"
    assert metadata["feature_count"] == 44
    assert metadata["threshold_business_optimal"] == 0.06
