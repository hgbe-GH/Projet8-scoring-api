"""FastAPI application exposing the Matchers completion-risk score."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError

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


@app.middleware("http")
async def record_monitoring_start(request: Request, call_next):
    """Record the start time of prediction requests for end-to-end latency."""
    if request.url.path == "/predict":
        request.state.monitoring_started_at = time.perf_counter()
    return await call_next(request)


def request_latency_ms(request: Request) -> float:
    """Return elapsed prediction-request time, including validation."""
    started_at = getattr(request.state, "monitoring_started_at", None)
    if started_at is None:
        return 0.0
    return (time.perf_counter() - started_at) * 1000


@app.exception_handler(RequestValidationError)
async def log_validation_error(
    request: Request, error: RequestValidationError
):
    """Log invalid prediction calls without retaining their raw payload."""
    if request.url.path == "/predict":
        service: ModelService | None = app.state.model_service
        model_version = service.model_version if service is not None else "unavailable"
        app.state.logger.log_error(
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            latency_ms=request_latency_ms(request),
            model_version=model_version,
            error_code="validation_error",
        )
    return await request_validation_exception_handler(request, error)


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
def predict(payload: PredictionRequest, http_request: Request) -> PredictionResponse:
    """Validate one dossier and return its completion-failure risk score."""
    service: ModelService | None = app.state.model_service
    if service is None:
        app.state.logger.log_error(
            http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
            latency_ms=request_latency_ms(http_request),
            model_version="unavailable",
            error_code="model_unavailable",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scoring model is unavailable.",
        )

    try:
        result = service.predict(payload)
    except Exception as error:
        app.state.logger.log_error(
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            latency_ms=request_latency_ms(http_request),
            model_version=service.model_version,
            error_code="prediction_failed",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Prediction failed.",
        ) from error

    app.state.logger.log_prediction(
        features=payload.model_dump(),
        risk_score=result.risk_score,
        risk_flag=result.risk_flag,
        latency_ms=request_latency_ms(http_request),
        model_version=result.model_version,
    )
    return PredictionResponse(
        risk_score=result.risk_score,
        threshold=result.threshold,
        risk_flag=result.risk_flag,
        model_name=result.model_name,
        model_version=result.model_version,
    )
