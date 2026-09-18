import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.analyze_monitoring import load_reference_events
from scoring_api.monitoring_storage import import_render_export


def test_analysis_writes_evidently_and_sqlite_evidence(tmp_path) -> None:
    from scripts.generate_monitoring_demo import generate_demo

    reference, export = generate_demo(tmp_path)
    database = tmp_path / "monitoring.db"
    assert import_render_export(export, database) == 30
    output = tmp_path / "reports"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/analyze_monitoring.py",
            "--database", str(database),
            "--reference", str(reference),
            "--output-dir", str(output),
        ],
        cwd=Path(__file__).parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads((output / "latest_report.json").read_text())
    assert report["storage"]["row_count"] == 30
    assert report["evidently"]["status"] == "ok"
    assert report["evidently"]["drifted_columns"] >= 1
    assert (output / "evidently_report.html").is_file()


@pytest.mark.parametrize("sources", [("training", "synthetic_demo"), (None, None), ("", "")])
def test_reference_requires_a_single_explicit_source(tmp_path, sources) -> None:
    reference = tmp_path / "reference.jsonl"
    reference.write_text(
        json.dumps({"status": "success", "features": {}, "reference_source": sources[0]})
        + "\n"
        + json.dumps({"status": "success", "features": {}, "reference_source": sources[1]})
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="reference_source"):
        load_reference_events(reference)
