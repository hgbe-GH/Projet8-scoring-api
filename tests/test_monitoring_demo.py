import json
import subprocess
import sys
from pathlib import Path


def test_monitoring_demo_generator_creates_shifted_reference_and_production(tmp_path) -> None:
    subprocess.run(
        [
            sys.executable,
            "scripts/generate_monitoring_demo.py",
            "--output-dir",
            str(tmp_path),
        ],
        check=True,
        cwd=Path(__file__).parents[1],
    )

    reference_path = tmp_path / "reference_events.jsonl"
    production_path = tmp_path / "render_demo_export.jsonl"
    reference = [json.loads(line) for line in reference_path.read_text().splitlines()]
    production = [
        json.loads(json.loads(line)["message"].removeprefix("ML_EVENT "))
        for line in production_path.read_text().splitlines()
    ]

    assert len(reference) >= 30
    assert len(production) >= 30
    assert reference[0]["reference_source"] == "synthetic_demo"
    assert min(event["features"]["heures_prevues"] for event in production) > max(
        event["features"]["heures_prevues"] for event in reference
    )
    assert "hybride" in {event["features"]["modalite"] for event in production}
    assert "hybride" not in {event["features"]["modalite"] for event in reference}
