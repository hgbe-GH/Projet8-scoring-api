"""Metrics for local prediction monitoring and demonstrative data drift."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import numpy as np

NUMERIC_DRIFT_FEATURES = (
    "heures_prevues",
    "montant_demande_eur",
    "pct_financement_demande",
)
CATEGORICAL_DRIFT_FEATURES = ("modalite", "source_lead", "type_financement")
PSI_ALERT_THRESHOLD = 0.20
UNKNOWN_CATEGORY_ALERT_THRESHOLD = 0.05
ERROR_RATE_ALERT_THRESHOLD = 0.05
P95_LATENCY_ALERT_THRESHOLD_MS = 1000.0
MINIMUM_DRIFT_SAMPLE_SIZE = 10


def population_stability_index(
    reference: list[float], production: list[float], bins: int = 10
) -> float:
    """Measure distribution shift with reference quantile bins."""
    if not reference or not production:
        raise ValueError("PSI requires non-empty reference and production samples")

    quantiles = np.quantile(reference, np.linspace(0, 1, bins + 1))
    internal_edges = np.unique(quantiles[1:-1])
    bin_edges = np.concatenate(([-np.inf], internal_edges, [np.inf]))
    reference_proportions = np.histogram(reference, bins=bin_edges)[0] / len(reference)
    production_proportions = np.histogram(production, bins=bin_edges)[0] / len(
        production
    )
    epsilon = 1e-6
    safe_reference = np.clip(reference_proportions, epsilon, None)
    safe_production = np.clip(production_proportions, epsilon, None)
    return float(
        np.sum(
            (safe_production - safe_reference)
            * np.log(safe_production / safe_reference)
        )
    )


def unknown_category_rate(reference: list[str], production: list[str]) -> float:
    """Return the fraction of production values absent from the reference."""
    if not production:
        return 0.0
    reference_categories = set(reference)
    return sum(value not in reference_categories for value in production) / len(production)


def operational_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize request volume, errors and observed end-to-end latency."""
    total_events = len(events)
    error_count = sum(event.get("status") != "success" for event in events)
    latencies = [float(event["latency_ms"]) for event in events if "latency_ms" in event]
    error_rate = error_count / total_events if total_events else 0.0
    median_latency = float(np.median(latencies)) if latencies else None
    p95_latency = float(np.percentile(latencies, 95)) if latencies else None

    return {
        "total_events": total_events,
        "error_count": error_count,
        "error_rate": error_rate,
        "error_rate_alert": error_rate > ERROR_RATE_ALERT_THRESHOLD,
        "median_latency_ms": median_latency,
        "p95_latency_ms": p95_latency,
        "p95_latency_alert": (
            p95_latency > P95_LATENCY_ALERT_THRESHOLD_MS
            if p95_latency is not None
            else None
        ),
    }


def drift_summary(
    reference_events: list[dict[str, Any]], production_events: list[dict[str, Any]]
) -> dict[str, Any]:
    """Compare successful prediction inputs and surface usable drift alerts."""
    reference_features = _successful_features(reference_events)
    production_features = _successful_features(production_events)
    return {
        "reference_successful_events": len(reference_features),
        "production_successful_events": len(production_features),
        "numeric": {
            feature: _numeric_drift(feature, reference_features, production_features)
            for feature in NUMERIC_DRIFT_FEATURES
        },
        "categorical": {
            feature: _categorical_drift(feature, reference_features, production_features)
            for feature in CATEGORICAL_DRIFT_FEATURES
        },
    }


def build_monitoring_report(
    reference_events: list[dict[str, Any]], production_events: list[dict[str, Any]]
) -> dict[str, Any]:
    """Build the machine-readable monitoring result used by the CLI report."""
    reference_source = next(
        (
            str(event["reference_source"])
            for event in reference_events
            if "reference_source" in event
        ),
        "unknown",
    )
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "reference_source": reference_source,
        "operational": operational_summary(production_events),
        "drift": drift_summary(reference_events, production_events),
    }


def _successful_features(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        features
        for event in events
        if event.get("status") == "success"
        and isinstance((features := event.get("features")), dict)
    ]


def _numeric_drift(
    feature: str,
    reference_features: list[dict[str, Any]],
    production_features: list[dict[str, Any]],
) -> dict[str, Any]:
    reference = _numeric_values(reference_features, feature)
    production = _numeric_values(production_features, feature)
    if min(len(reference), len(production)) < MINIMUM_DRIFT_SAMPLE_SIZE:
        return {
            "status": "insufficient_data",
            "reference_count": len(reference),
            "production_count": len(production),
            "psi": None,
            "alert": None,
        }

    psi = population_stability_index(reference, production)
    return {
        "status": "ok",
        "reference_count": len(reference),
        "production_count": len(production),
        "psi": psi,
        "alert": psi >= PSI_ALERT_THRESHOLD,
    }


def _categorical_drift(
    feature: str,
    reference_features: list[dict[str, Any]],
    production_features: list[dict[str, Any]],
) -> dict[str, Any]:
    reference = _string_values(reference_features, feature)
    production = _string_values(production_features, feature)
    if min(len(reference), len(production)) < MINIMUM_DRIFT_SAMPLE_SIZE:
        return {
            "status": "insufficient_data",
            "reference_count": len(reference),
            "production_count": len(production),
            "unknown_category_rate": None,
            "alert": None,
        }

    rate = unknown_category_rate(reference, production)
    return {
        "status": "ok",
        "reference_count": len(reference),
        "production_count": len(production),
        "unknown_category_rate": rate,
        "alert": rate >= UNKNOWN_CATEGORY_ALERT_THRESHOLD,
    }


def _numeric_values(features: list[dict[str, Any]], feature: str) -> list[float]:
    return [
        float(value)
        for row in features
        if isinstance((value := row.get(feature)), int | float)
    ]


def _string_values(features: list[dict[str, Any]], feature: str) -> list[str]:
    return [value for row in features if isinstance((value := row.get(feature)), str)]
