"""Local, durable storage for structured prediction-monitoring events."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from scoring_api.logging_service import EVENT_PREFIX

REQUIRED_EVENT_FIELDS = {
    "schema_version",
    "event_id",
    "timestamp",
    "event_type",
    "status",
    "http_status",
    "latency_ms",
    "model_version",
}


def initialize_database(database_path: Path) -> None:
    """Create the local monitoring table when it does not already exist."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS prediction_events (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                status TEXT NOT NULL,
                http_status INTEGER NOT NULL,
                latency_ms REAL NOT NULL,
                model_version TEXT NOT NULL,
                features_json TEXT,
                risk_score REAL,
                risk_flag INTEGER,
                error_code TEXT
            )
            """
        )


def iter_json_values(raw_text: str) -> Iterator[dict[str, Any]]:
    """Yield log objects from JSONL, concatenated JSON, or a JSON array."""
    decoder = json.JSONDecoder()
    position = 0

    while position < len(raw_text):
        while position < len(raw_text) and raw_text[position].isspace():
            position += 1
        if position == len(raw_text):
            return

        try:
            value, position = decoder.raw_decode(raw_text, position)
        except json.JSONDecodeError as error:
            raise ValueError("Render export is not valid JSON") from error

        entries = value if isinstance(value, list) else [value]
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("Render export entries must be JSON objects")
            yield entry


def import_render_export(export_path: Path, database_path: Path) -> int:
    """Import marked Render log events once and return the inserted row count."""
    raw_export = export_path.read_text(encoding="utf-8")
    events = [
        _parse_monitoring_event(envelope)
        for envelope in iter_json_values(raw_export)
        if _is_monitoring_envelope(envelope)
    ]
    initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        before_changes = connection.total_changes
        connection.executemany(
            """
            INSERT OR IGNORE INTO prediction_events (
                event_id, timestamp, event_type, status, http_status, latency_ms,
                model_version, features_json, risk_score, risk_flag, error_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [_event_row(event) for event in events],
        )
        return connection.total_changes - before_changes


def list_prediction_events(database_path: Path) -> list[dict[str, Any]]:
    """Return locally stored events in chronological order for analysis."""
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM prediction_events ORDER BY timestamp, event_id"
        ).fetchall()

    return [_row_to_event(row) for row in rows]


def storage_evidence(database_path: Path) -> dict[str, Any]:
    """Read durable row counts and bounds through a fresh SQLite connection."""
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT COUNT(*),
                   SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END),
                   MIN(timestamp), MAX(timestamp)
            FROM prediction_events
            """
        ).fetchone()
        latest = connection.execute(
            "SELECT event_id FROM prediction_events ORDER BY timestamp DESC, event_id DESC LIMIT 1"
        ).fetchone()
    return {
        "row_count": row[0],
        "successful_count": row[1] or 0,
        "earliest_timestamp": row[2],
        "latest_timestamp": row[3],
        "latest_event_id": latest[0] if latest else None,
    }


def _is_monitoring_envelope(envelope: dict[str, Any]) -> bool:
    message = envelope.get("message")
    return isinstance(message, str) and message.startswith(EVENT_PREFIX)


def _parse_monitoring_event(envelope: dict[str, Any]) -> dict[str, Any]:
    message = envelope["message"]
    try:
        event = json.loads(message.removeprefix(EVENT_PREFIX))
    except json.JSONDecodeError as error:
        raise ValueError("Malformed ML_EVENT payload") from error

    if not isinstance(event, dict) or not REQUIRED_EVENT_FIELDS.issubset(event):
        raise ValueError("Malformed ML_EVENT payload")
    return event


def _event_row(event: dict[str, Any]) -> tuple[Any, ...]:
    features = event.get("features")
    return (
        event["event_id"],
        event["timestamp"],
        event["event_type"],
        event["status"],
        event["http_status"],
        event["latency_ms"],
        event["model_version"],
        json.dumps(features, ensure_ascii=False, sort_keys=True)
        if features is not None
        else None,
        event.get("risk_score"),
        int(event["risk_flag"]) if "risk_flag" in event else None,
        event.get("error_code"),
    )


def _row_to_event(row: sqlite3.Row) -> dict[str, Any]:
    event = dict(row)
    event["features"] = (
        json.loads(event.pop("features_json"))
        if event["features_json"] is not None
        else None
    )
    if event["risk_flag"] is not None:
        event["risk_flag"] = bool(event["risk_flag"])
    return event
