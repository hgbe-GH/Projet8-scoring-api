from pathlib import Path


def test_ci_workflow_has_test_and_build_jobs_while_render_deploys_after_checks() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "PYTHONPATH=src pytest -v" in workflow
    assert "bash tests/test_container_smoke.sh" in workflow
    assert "Hugging Face" not in workflow
    assert "HF_TOKEN" not in workflow
    assert "HF_SPACE_ID" not in workflow
