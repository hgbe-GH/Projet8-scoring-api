"""Local Streamlit dashboard for scoring operations and data drift."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from scoring_api.monitoring_config import DATABASE_PATH, REPORT_DIR
from scoring_api.monitoring_storage import storage_evidence


def _read_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _drift_rows(report: dict) -> list[dict]:
    rows = []
    for feature, metric in report["drift"]["numeric"].items():
        rows.append({
            "Variable": feature, "Mesure": "PSI", "Valeur": metric["psi"],
            "État": metric["status"], "Alerte": metric["alert"],
        })
    for feature, metric in report["drift"]["categorical"].items():
        rows.append({
            "Variable": feature, "Mesure": "Catégories inconnues",
            "Valeur": metric["unknown_category_rate"],
            "État": metric["status"], "Alerte": metric["alert"],
        })
    return rows


def main() -> None:
    st.set_page_config(page_title="Monitoring du scoring", layout="wide")
    st.title("Monitoring du scoring")
    report_path = Path(os.getenv("MONITORING_REPORT_PATH", REPORT_DIR / "latest_report.json"))
    database_path = Path(os.getenv("MONITORING_DATABASE_PATH", DATABASE_PATH))
    if not report_path.is_file():
        st.error(f"Rapport introuvable : {report_path}. Lancez scripts/analyze_monitoring.py.")
        st.stop()

    report = _read_report(report_path)
    if "evidently" not in report:
        st.error(
            "Rapport ancien format : relancez scripts/analyze_monitoring.py "
            "pour calculer Evidently."
        )
        st.stop()
    evidence = storage_evidence(database_path) if database_path.is_file() else None
    if evidence is not None and report.get("storage") != evidence:
        st.warning(
            "La base SQLite a changé depuis ce rapport. "
            "Relancez l'analyse pour actualiser le drift."
        )
    st.caption(f"Rapport du {report['generated_at']} · Référence : {report['reference_source']}")
    if report["reference_source"] == "synthetic_demo":
        st.warning(
            "Référence synthétique : démonstration du pipeline, "
            "sans conclusion sur la dérive réelle."
        )

    operational = report["operational"]
    columns = st.columns(4)
    columns[0].metric("Appels", operational["total_events"])
    columns[1].metric("Taux d'erreur", f"{operational['error_rate']:.1%}")
    median = operational["median_latency_ms"]
    p95 = operational["p95_latency_ms"]
    columns[2].metric("Latence médiane", f"{median:.1f} ms" if median is not None else "—")
    columns[3].metric("Latence p95", f"{p95:.1f} ms" if p95 is not None else "—")

    st.subheader("Dérive des données")
    drift = report["drift"]
    evidently = report["evidently"]
    st.write(
        f"Prédictions comparées : {drift['reference_successful_events']} en référence, "
        f"{drift['production_successful_events']} en production."
    )
    if evidently["status"] == "ok":
        st.metric(
            "Variables en drift selon Evidently",
            f"{evidently['drifted_columns']} / {len(evidently['columns'])}",
        )
        evidently_rows = [
            {"Variable": feature, "Méthode": result["method"],
             "Score": result["score"], "Seuil": result["threshold"],
             "Drift détecté": result["drift_detected"]}
            for feature, result in evidently["columns"].items()
        ]
        st.dataframe(
            pd.DataFrame(evidently_rows),
            hide_index=True,
            column_config={
                "Score": st.column_config.NumberColumn(format="%.3g"),
                "Seuil": st.column_config.NumberColumn(format="%.3g"),
            },
        )
    else:
        st.info(
            "Evidently : données insuffisantes pour conclure "
            "(10 lignes complètes minimum par jeu)."
        )

    st.caption("PSI ≥ 0,20 ou catégories inconnues ≥ 5 % : alerte locale.")
    st.dataframe(pd.DataFrame(_drift_rows(report)), hide_index=True)

    st.subheader("Preuve de persistance SQLite")
    if evidence is not None:
        st.write(f"Base : `{database_path}`")
        st.write(
            f"{evidence['row_count']} événements enregistrés, dont "
            f"{evidence['successful_count']} prédictions réussies."
        )
        st.write(
            f"Du {evidence['earliest_timestamp']} au {evidence['latest_timestamp']} · "
            f"Dernier ID : `{evidence['latest_event_id']}`"
        )
    else:
        st.warning(f"Base SQLite introuvable : {database_path}")

    html_path = report_path.parent / "evidently_report.html"
    if html_path.is_file():
        st.download_button(
            "Télécharger le rapport Evidently HTML",
            html_path.read_bytes(),
            file_name="evidently_report.html",
            mime="text/html",
        )


if __name__ == "__main__":
    main()
