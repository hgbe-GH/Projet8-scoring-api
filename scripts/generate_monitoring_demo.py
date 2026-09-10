"""Generate deterministic, non-sensitive monitoring data for the local PoC."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from scoring_api.logging_service import EVENT_PREFIX

REFERENCE_SOURCE = "synthetic_demo"
SAMPLE_SIZE = 30


def parse_arguments() -> argparse.Namespace:
    """Return the target directory for generated demonstration data."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/monitoring"))
    return parser.parse_args()


def prediction_event(
    event_id: str,
    timestamp: str,
    features: dict[str, Any],
    *,
    reference: bool = False,
) -> dict[str, Any]:
    """Build a privacy-safe successful prediction event compatible with the importer."""
    event: dict[str, Any] = {
        "schema_version": 1,
        "event_id": event_id,
        "timestamp": timestamp,
        "event_type": "prediction",
        "status": "success",
        "http_status": 200,
        "latency_ms": 25.0,
        "model_version": "2026-06-15",
        "features": features,
        "risk_score": 0.12,
        "risk_flag": True,
    }
    if reference:
        event["reference_source"] = REFERENCE_SOURCE
    return event


def generate_demo(output_dir: Path) -> tuple[Path, Path]:
    """Write a stable reference JSONL and Render-shaped production export."""
    randomizer = random.Random(20260910)
    output_dir.mkdir(parents=True, exist_ok=True)
    reference_path = output_dir / "reference_events.jsonl"
    production_path = output_dir / "render_demo_export.jsonl"

    reference_events = []
    production_envelopes = []
    for index in range(SAMPLE_SIZE):
        reference_features = {
            "heures_prevues": randomizer.randint(15, 35),
            "montant_demande_eur": randomizer.randint(1000, 4000),
            "pct_financement_demande": round(randomizer.uniform(0.55, 0.85), 2),
            "modalite": "standard" if index % 2 == 0 else "distance",
            "source_lead": "direct" if index % 2 == 0 else "partenaire",
            "type_financement": "classique",
        }
        reference_events.append(
            prediction_event(
                f"reference-{index}",
                f"2026-09-01T12:{index:02d}:00+00:00",
                reference_features,
                reference=True,
            )
        )
        production_features = {
            "heures_prevues": randomizer.randint(60, 90),
            "montant_demande_eur": randomizer.randint(1000, 4000),
            "pct_financement_demande": round(randomizer.uniform(0.55, 0.85), 2),
            "modalite": "hybride" if index % 2 == 0 else "standard",
            "source_lead": "direct" if index % 2 == 0 else "partenaire",
            "type_financement": "classique",
        }
        production_event = prediction_event(
            f"production-{index}",
            f"2026-09-10T12:{index:02d}:00+00:00",
            production_features,
        )
        production_envelopes.append(
            {"message": EVENT_PREFIX + json.dumps(production_event, ensure_ascii=False)}
        )

    reference_path.write_text(
        "\n".join(json.dumps(event, ensure_ascii=False) for event in reference_events)
        + "\n",
        encoding="utf-8",
    )
    production_path.write_text(
        "\n".join(
            json.dumps(envelope, ensure_ascii=False) for envelope in production_envelopes
        )
        + "\n",
        encoding="utf-8",
    )
    return reference_path, production_path


def main() -> int:
    """Create demo files and print their location."""
    reference_path, production_path = generate_demo(parse_arguments().output_dir)
    print(f"Reference events written to {reference_path}.")
    print(f"Render demo export written to {production_path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
