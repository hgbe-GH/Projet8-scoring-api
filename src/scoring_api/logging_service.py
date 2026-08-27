"""Structured, local production-event logging for scoring requests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class PredictionEventLogger:
    """Append prediction events in a JSON-lines file excluded from Git."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def log_prediction(
        self,
        *,
        features: dict[str, Any],
        risk_score: float,
        risk_flag: bool,
        duration_ms: float,
        model_version: str,
    ) -> None:
        """Store a successful inference event containing validated model inputs."""
        self._append(
            {
                "timestamp": self._timestamp(),
                "event_type": "prediction",
                "status": "success",
                "features": features,
                "risk_score": risk_score,
                "risk_flag": risk_flag,
                "duration_ms": duration_ms,
                "model_version": model_version,
            }
        )

    def log_error(self, *, duration_ms: float, model_version: str) -> None:
        """Store an opaque operational error without leaking internal details."""
        self._append(
            {
                "timestamp": self._timestamp(),
                "event_type": "prediction",
                "status": "error",
                "duration_ms": duration_ms,
                "model_version": model_version,
            }
        )

    def _append(self, event: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(UTC).isoformat()
