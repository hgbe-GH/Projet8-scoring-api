from pathlib import Path


def test_ci_workflow_has_test_build_smoke_and_deploy() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "PYTHONPATH=src pytest -v" in workflow
    assert "bash tests/test_container_smoke.sh" in workflow
    assert "HF_TOKEN" in workflow
    assert "HF_SPACE_ID" in workflow
