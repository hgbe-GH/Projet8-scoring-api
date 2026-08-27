"""FastAPI application exposing the Matchers completion-risk score."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, status

from scoring_api.logging_service import PredictionEventLogger
from scoring_api.model_service import ModelService
from scoring_api.schemas import PredictionRequest, PredictionResponse

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = PROJECT_ROOT / "models" / "matchers_option_a_model.joblib"
METADATA_PATH = PROJECT_ROOT / "models" / "matchers_option_a_metadata.json"
LOG_PATH = PROJECT_ROOT / "logs" / "predictions.jsonl"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load the shared model immediately before the application accepts traffic."""
    app.state.logger = PredictionEventLogger(LOG_PATH)
    app.state.model_service = None

    try:
        app.state.model_service = ModelService.from_paths(MODEL_PATH, METADATA_PATH)
    except (OSError, ValueError):
        app.state.model_service = None

    yield


app = FastAPI(
    title="Matchers scoring API",
    description="Predicts the risk that a gained dossier will not reach completion.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    """Return readiness and the version of the currently loaded model."""
    service: ModelService | None = app.state.model_service
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scoring model is unavailable.",
        )

    return {
        "status": "ok",
        "model_name": service.model_name,
        "model_version": service.model_version,
    }


@app.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest) -> PredictionResponse:
    """Validate one dossier and return its completion-failure risk score."""
    service: ModelService | None = app.state.model_service
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scoring model is unavailable.",
        )

    started_at = time.perf_counter()
    try:
        result = service.predict(request)
    except Exception as error:
        duration_ms = (time.perf_counter() - started_at) * 1000
        app.state.logger.log_error(
            duration_ms=duration_ms,
            model_version=service.model_version,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Prediction failed.",
        ) from error

    duration_ms = (time.perf_counter() - started_at) * 1000
    app.state.logger.log_prediction(
        features=request.model_dump(),
        risk_score=result.risk_score,
        risk_flag=result.risk_flag,
        duration_ms=duration_ms,
        model_version=result.model_version,
    )
    return PredictionResponse(
        risk_score=result.risk_score,
        threshold=result.threshold,
        risk_flag=result.risk_flag,
        model_name=result.model_name,
        model_version=result.model_version,
    )

