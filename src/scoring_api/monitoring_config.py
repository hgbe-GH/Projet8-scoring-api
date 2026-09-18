"""Shared local monitoring paths and drift configuration."""

from pathlib import Path

DATABASE_PATH = Path("data/monitoring/monitoring.db")
REFERENCE_PATH = Path("data/monitoring/reference_events.jsonl")
REPORT_DIR = Path("reports/monitoring")

NUMERIC_DRIFT_FEATURES = (
    "heures_prevues",
    "montant_demande_eur",
    "pct_financement_demande",
)
CATEGORICAL_DRIFT_FEATURES = ("modalite", "source_lead", "type_financement")
MINIMUM_DRIFT_SAMPLE_SIZE = 10
PSI_ALERT_THRESHOLD = 0.20
UNKNOWN_CATEGORY_ALERT_THRESHOLD = 0.05
ERROR_RATE_ALERT_THRESHOLD = 0.05
P95_LATENCY_ALERT_THRESHOLD_MS = 1000.0
EVIDENTLY_CATEGORICAL_METHOD = "jensenshannon"
EVIDENTLY_CATEGORICAL_THRESHOLD = 0.1
