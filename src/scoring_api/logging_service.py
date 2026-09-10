"""Structured, local production-event logging for scoring requests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


EVENT_PREFIX = "ML_EVENT "


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
        latency_ms: float,
        model_version: str,
    ) -> None:
        """Store a successful inference event containing validated model inputs."""
        event = self._base_event(
            status="success",
            http_status=200,
            latency_ms=latency_ms,
            model_version=model_version,
        )
        event.update(
            {
                "features": features,
                "risk_score": risk_score,
                "risk_flag": risk_flag,
            }
        )
        self._append(event)

    def log_error(
        self,
        *,
        http_status: int,
        latency_ms: float,
        model_version: str,
        error_code: str,
    ) -> None:
        """Store an opaque operational error without leaking internal details."""
        event = self._base_event(
            status="error",
            http_status=http_status,
            latency_ms=latency_ms,
            model_version=model_version,
        )
        event["error_code"] = error_code
        self._append(event)

    @classmethod
    def _base_event(
        cls,
        *,
        status: str,
        http_status: int,
        latency_ms: float,
        model_version: str,
    ) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "event_id": uuid4().hex,
            "timestamp": cls._timestamp(),
            "event_type": "prediction",
            "status": status,
            "http_status": http_status,
            "latency_ms": latency_ms,
            "model_version": model_version,
        }

    def _append(self, event: dict[str, Any]) -> None:
        serialized_event = json.dumps(event, ensure_ascii=False, sort_keys=True)
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as file:
                file.write(serialized_event + "\n")
        except OSError:
            pass

        try:
            print(f"{EVENT_PREFIX}{serialized_event}", flush=True)
        except OSError:
            pass

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(UTC).isoformat()
