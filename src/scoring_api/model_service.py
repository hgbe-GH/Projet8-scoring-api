"""Loading and inference for the versioned scoring model."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from scoring_api.schemas import PredictionRequest


@dataclass(frozen=True)
class PredictionResult:
    """Result of a single scoring operation."""

    risk_score: float
    threshold: float
    risk_flag: bool
    model_name: str
    model_version: str


class ModelService:
    """A loaded model and the metadata that defines its inference contract."""

    def __init__(self, model: Any, metadata: dict[str, Any]) -> None:
        self._model = model
        self._metadata = metadata

    @classmethod
    def from_paths(cls, model_path: Path, metadata_path: Path) -> ModelService:
        """Load both artefacts once when the application starts."""
        model = joblib.load(model_path)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        return cls(model=model, metadata=metadata)

    @property
    def model_name(self) -> str:
        return str(self._metadata["champion_name"])

    @property
    def model_version(self) -> str:
        return str(self._metadata["snapshot_date"])

    def predict(self, request: PredictionRequest) -> PredictionResult:
        """Score one validated request with the model's feature order."""
        frame = pd.DataFrame([request.model_dump()])
        feature_columns = self._metadata["feature_columns"]
        probability = float(self._model.predict_proba(frame.loc[:, feature_columns])[:, 1][0])
        threshold = float(self._metadata["threshold_business_optimal"])

        return PredictionResult(
            risk_score=probability,
            threshold=threshold,
            risk_flag=probability >= threshold,
            model_name=self.model_name,
            model_version=self.model_version,
        )
