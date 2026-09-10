import pytest

from scoring_api.monitoring_analysis import (
    drift_summary,
    operational_summary,
    population_stability_index,
    unknown_category_rate,
)


def _success_event(
    *,
    event_id: str,
    heures_prevues: float,
    modalite: str = "standard",
) -> dict[str, object]:
    return {
        "event_id": event_id,
        "status": "success",
        "http_status": 200,
        "latency_ms": 20.0,
        "features": {
            "heures_prevues": heures_prevues,
            "montant_demande_eur": 2000.0,
            "pct_financement_demande": 0.8,
            "modalite": modalite,
            "source_lead": "direct",
            "type_financement": "standard",
        },
    }


def test_population_stability_index_is_zero_for_matching_distributions() -> None:
    reference = list(range(1, 101))

    assert population_stability_index(reference, reference) == pytest.approx(0.0)


def test_population_stability_index_detects_a_shifted_distribution() -> None:
    reference = list(range(1, 101))
    production = list(range(101, 201))

    assert population_stability_index(reference, production) >= 0.20


def test_unknown_category_rate_detects_new_values() -> None:
    rate = unknown_category_rate(
        reference=["standard", "distance"],
        production=["standard", "nouvelle-valeur"],
    )

    assert rate == 0.5


def test_operational_summary_reports_error_rate_and_p95_latency() -> None:
    events = [
        {"status": "success", "latency_ms": 20.0},
        {"status": "success", "latency_ms": 40.0},
        {"status": "error", "latency_ms": 1400.0},
    ]

    summary = operational_summary(events)

    assert summary["error_rate"] == pytest.approx(1 / 3)
    assert summary["p95_latency_ms"] == pytest.approx(1264.0)
    assert summary["p95_latency_alert"] is True


def test_drift_summary_reports_insufficient_data_instead_of_no_drift() -> None:
    reference = [_success_event(event_id="reference-1", heures_prevues=20.0)]
    production = [_success_event(event_id="production-1", heures_prevues=50.0)]

    summary = drift_summary(reference, production)

    assert summary["numeric"]["heures_prevues"]["status"] == "insufficient_data"
    assert summary["numeric"]["heures_prevues"]["alert"] is None
