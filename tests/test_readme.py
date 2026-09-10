from pathlib import Path


def test_readme_documents_the_local_monitoring_flow() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    for required_term in (
        "Render",
        "monitoring.db",
        "import_render_logs.py",
        "analyze_monitoring.py",
        "PSI",
        "synthetic",
        "RGPD",
    ):
        assert required_term in readme
