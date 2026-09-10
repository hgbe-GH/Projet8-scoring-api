# Local Monitoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist Render prediction events locally and produce a repeatable report of operational anomalies and demonstrative data drift.

**Architecture:** The API emits one privacy-preserving JSON event to local JSONL and standard output for every `/predict` result. A local importer extracts `ML_EVENT ` records from a Render log export into SQLite. Pure analysis functions compare successful inputs to a synthetic reference and write JSON/Markdown reports.

**Tech Stack:** FastAPI, Pydantic, Python standard library (`sqlite3`, `json`, `argparse`), NumPy, Pytest, Render CLI.

---

### Task 1: Emit the full structured event from the API

**Files:**

- Modify: `src/scoring_api/logging_service.py`
- Modify: `src/scoring_api/main.py`
- Modify: `tests/test_logging_service.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write failing event-contract tests**

Update `tests/test_logging_service.py` to require these keys on a successful call to `log_prediction`: `schema_version == 1`, non-empty `event_id`, `timestamp`, `event_type == "prediction"`, `status == "success"`, `http_status == 200`, `features`, `risk_score`, `risk_flag`, `latency_ms`, and `model_version`. Capture stdout with `capsys` and require it to start with `ML_EVENT `.

Add an error test for `log_error(http_status=422, latency_ms=2.5, model_version="2026-06-15", error_code="validation_error")`. It must assert `status == "error"`, `http_status == 422`, correct `error_code`, and absence of `features` and `error_detail`.

- [ ] **Step 2: Verify the tests fail first**

Run: `PYTHONPATH=src pytest -v tests/test_logging_service.py`

Expected: FAIL because the current logger exposes `duration_ms`, no event id/schema/status code and no stdout event.

- [ ] **Step 3: Implement the normalized event builder**

In `src/scoring_api/logging_service.py`, define `EVENT_PREFIX = "ML_EVENT "`. Add a private method that returns the common fields using `uuid.uuid4().hex` and `datetime.now(UTC).isoformat()`. Rename the public latency argument to `latency_ms`; success calls use `http_status=200`; errors require `http_status` and `error_code`.

Keep `_append` responsible for both destinations:

```python
serialized_event = json.dumps(event, ensure_ascii=False, sort_keys=True)
with self._path.open("a", encoding="utf-8") as file:
    file.write(serialized_event + "\n")
print(f"{EVENT_PREFIX}{serialized_event}", flush=True)
```

No error method accepts a request body or exception message.

- [ ] **Step 4: Verify the logger is green**

Run: `PYTHONPATH=src pytest -v tests/test_logging_service.py`

Expected: PASS.

- [ ] **Step 5: Write failing API error tests**

In `tests/test_api.py`, add:

```python
def test_predict_logs_an_opaque_validation_error(valid_payload):
    valid_payload.pop("funder_nom")
    with TestClient(app) as client:
        response = client.post("/predict", json=valid_payload)
    assert response.status_code == 422
    event = latest_logged_event()
    assert event["http_status"] == 422
    assert event["error_code"] == "validation_error"
    assert "features" not in event
```

Add an analogous test that monkeypatches `app.state.model_service.predict` to raise `RuntimeError`, then requires a `500` event with `error_code == "prediction_failed"`, no feature body and no error detail.

- [ ] **Step 6: Verify the API failure tests fail**

Run: `PYTHONPATH=src pytest -v tests/test_api.py -k logs`

Expected: FAIL because default FastAPI validation handling does not emit a monitoring event.

- [ ] **Step 7: Implement one event per `/predict` outcome**

In `src/scoring_api/main.py`:

1. Import `Request`, `RequestValidationError`, `JSONResponse` and `jsonable_encoder`.
2. Add middleware that records `time.perf_counter()` as `request.state.monitoring_started_at` for `/predict`.
3. Add a helper that converts this start value to `latency_ms`.
4. Register a `RequestValidationError` handler; for `/predict` it calls `log_error(http_status=422, error_code="validation_error", latency_ms=...)` and returns FastAPI's normal JSON error body.
5. Start timing before the model availability check; log `503/model_unavailable`, `500/prediction_failed`, or the success event. Use validated `request.model_dump()` only for successful predictions.

Preserve the existing status codes and `PredictionResponse` body. Logging failures must be caught inside the logger so a successful prediction response remains successful.

- [ ] **Step 8: Run regression tests**

Run: `PYTHONPATH=src pytest -v tests/test_logging_service.py tests/test_api.py`

Expected: PASS.

- [ ] **Step 9: Commit the API event contract**

```bash
git add src/scoring_api/logging_service.py src/scoring_api/main.py tests/test_logging_service.py tests/test_api.py
git commit -m "feat: emit structured monitoring events"
```

### Task 2: Import Render exports into idempotent SQLite storage

**Files:**

- Create: `src/scoring_api/monitoring_storage.py`
- Create: `scripts/import_render_logs.py`
- Create: `tests/test_monitoring_storage.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write failing importer tests**

Create `tests/test_monitoring_storage.py` with `success_event()` returning a full event whose `event_id` is `event-1`. Test that an export containing one unrelated envelope plus `{"message": "ML_EVENT " + json.dumps(success_event())}` imports exactly one row. Call the importer twice and assert the second import returns zero, while `list_prediction_events()` returns only `event-1`.

Add a second test that writes two pretty-printed JSON objects directly one after another, the format emitted by `render logs -o json`, and asserts both marked messages are found. This fixes the parser contract before implementation.

- [ ] **Step 2: Verify the importer tests fail**

Run: `PYTHONPATH=src pytest -v tests/test_monitoring_storage.py`

Expected: FAIL because there is no storage module.

- [ ] **Step 3: Implement storage and parser**

Create `src/scoring_api/monitoring_storage.py` with:

```python
def initialize_database(database_path: Path) -> None: ...
def iter_json_values(raw_text: str) -> Iterator[dict[str, Any]]: ...
def import_render_export(export_path: Path, database_path: Path) -> int: ...
def list_prediction_events(database_path: Path) -> list[dict[str, Any]]: ...
```

Create a `prediction_events` SQLite table with `event_id TEXT PRIMARY KEY`, timestamp/status/status-code/latency/model-version scalar columns, `features_json TEXT`, result columns and `error_code`. Use `json.JSONDecoder().raw_decode` repeatedly after whitespace to accept JSONL and concatenated pretty objects. Retain only outer objects whose `message` starts `ML_EVENT `. Decode that suffix, validate required common keys, and `INSERT OR IGNORE` by event id. Rebuild `features` from `features_json` in `list_prediction_events`.

Create `scripts/import_render_logs.py` with required `--input` and optional `--database` defaulting to `data/monitoring/monitoring.db`; it calls the repository function, prints `Imported N new monitoring event(s).`, and exits non-zero for absent input or malformed marked payload.

- [ ] **Step 4: Exclude local monitoring data from version control**

Append exactly these rules to `.gitignore`:

```gitignore
data/monitoring/
reports/monitoring/
```

- [ ] **Step 5: Verify importer behavior**

Run: `PYTHONPATH=src pytest -v tests/test_monitoring_storage.py`

Expected: PASS, including the duplicate-import check.

- [ ] **Step 6: Commit the durable local store**

```bash
git add src/scoring_api/monitoring_storage.py scripts/import_render_logs.py tests/test_monitoring_storage.py .gitignore
git commit -m "feat: store exported Render events locally"
```

### Task 3: Calculate operational anomalies and data drift

**Files:**

- Create: `src/scoring_api/monitoring_analysis.py`
- Create: `scripts/analyze_monitoring.py`
- Create: `tests/test_monitoring_analysis.py`

- [ ] **Step 1: Write failing metric tests**

Create `tests/test_monitoring_analysis.py`. Require `population_stability_index([10, 10, 10, 10], [10, 10, 10, 10])` to be near zero; require a deliberately shifted second population to reach `0.20`. Test a categorical production list containing `"nouvelle-valeur"` versus a reference without it: rate `0.5`, alert true at threshold `0.05`. Test events with one 500 and latencies `[20, 40, 1400]`: error rate `1/3`, p95 close to `1264`, and latency alert true.

Add an insufficient-data test: fewer than ten successful reference or production events must return `status == "insufficient_data"`, never `alert == False`.

- [ ] **Step 2: Verify metric tests fail**

Run: `PYTHONPATH=src pytest -v tests/test_monitoring_analysis.py`

Expected: FAIL because no analysis module exists.

- [ ] **Step 3: Implement pure analysis functions**

Create `src/scoring_api/monitoring_analysis.py` with these constants:

```python
NUMERIC_DRIFT_FEATURES = ("heures_prevues", "montant_demande_eur", "pct_financement_demande")
CATEGORICAL_DRIFT_FEATURES = ("modalite", "source_lead", "type_financement")
PSI_ALERT_THRESHOLD = 0.20
UNKNOWN_CATEGORY_ALERT_THRESHOLD = 0.05
ERROR_RATE_ALERT_THRESHOLD = 0.05
P95_LATENCY_ALERT_THRESHOLD_MS = 1000.0
```

Implement `population_stability_index`, `unknown_category_rate`, `operational_summary`, `drift_summary`, and `build_monitoring_report`. Build ten reference quantile bins for PSI, use epsilon only to prevent zero division, and calculate p95 using `numpy.percentile(latencies, 95)`. `operational_summary` counts all stored outcomes, but drift uses only successful events with input features.

Create `scripts/analyze_monitoring.py` with `--database`, `--reference`, and `--output-dir` options. It reads reference JSONL and SQLite, writes `latest_report.json` and `latest_report.md`; the Markdown contains sample sizes, error rate, p95, every signal and alert, plus `Synthetic reference: demonstration only; not a production drift conclusion.` when reference metadata says `synthetic_demo`.

- [ ] **Step 4: Verify analysis behavior**

Run: `PYTHONPATH=src pytest -v tests/test_monitoring_analysis.py`

Expected: PASS.

- [ ] **Step 5: Commit drift and operational analysis**

```bash
git add src/scoring_api/monitoring_analysis.py scripts/analyze_monitoring.py tests/test_monitoring_analysis.py
git commit -m "feat: analyze operational anomalies and drift"
```

### Task 4: Build a reproducible demo and document operations

**Files:**

- Create: `scripts/generate_monitoring_demo.py`
- Create: `tests/test_monitoring_demo.py`
- Create: `tests/test_readme.py`
- Modify: `README.md`
- Modify: `docs/project-status.html`

- [ ] **Step 1: Write failing demo and README tests**

In `tests/test_monitoring_demo.py`, run the generator in `tmp_path`. Require `reference_events.jsonl` and `render_demo_export.jsonl`, each with at least 30 events. Require production to have a high `heures_prevues` distribution and a `modalite="hybride"` value not present in reference.

In `tests/test_readme.py`, assert README mentions `Render`, `monitoring.db`, `import_render_logs.py`, `analyze_monitoring.py`, `PSI`, `synthetic` and `RGPD`.

- [ ] **Step 2: Verify the new tests fail**

Run: `PYTHONPATH=src pytest -v tests/test_monitoring_demo.py tests/test_readme.py`

Expected: FAIL because generator and monitoring runbook do not exist.

- [ ] **Step 3: Implement the deterministic data demonstration**

Create `scripts/generate_monitoring_demo.py`. Use `random.Random(20260910)` and write `data/monitoring/reference_events.jsonl` and `data/monitoring/render_demo_export.jsonl`. The reference has metadata `reference_source="synthetic_demo"`; production envelopes each contain a `message` beginning `ML_EVENT `. Create at least 30 valid successful events per sample. Shift production `heures_prevues` high and add `modalite="hybride"` so the generated report contains both a numeric and categorical alert.

- [ ] **Step 4: Document the exact production and demo workflow**

Replace README's monitoring section with the flow `API Render → logs structurés → export local → SQLite → analyse`. Include:

```bash
render logs -r srv-daddn7oae00c739qdfq0 -o json > data/monitoring/render-export.json
PYTHONPATH=src python scripts/import_render_logs.py --input data/monitoring/render-export.json
PYTHONPATH=src python scripts/analyze_monitoring.py --reference data/monitoring/reference_events.jsonl
```

Document the generator command, all four alert thresholds, non-versioning of databases/exports, RGPD/retention limits and the fact that synthetic reference is a pipeline demonstration only. Update `docs/project-status.html` to mark logging, local storage and first drift measurement complete, while retaining the synthetic-reference limitation.

- [ ] **Step 5: Run all local verification**

```bash
PYTHONPATH=src pytest -v
PYTHONPATH=src python scripts/generate_monitoring_demo.py
PYTHONPATH=src python scripts/import_render_logs.py --input data/monitoring/render_demo_export.jsonl
PYTHONPATH=src python scripts/analyze_monitoring.py --reference data/monitoring/reference_events.jsonl
test -f reports/monitoring/latest_report.json
test -f reports/monitoring/latest_report.md
bash tests/test_container_smoke.sh
```

Expected: all tests pass; importer reports new events; reports contain drift alerts; Docker `/health` responds with status `ok`.

- [ ] **Step 6: Commit demo and documentation**

```bash
git add scripts/generate_monitoring_demo.py tests/test_monitoring_demo.py tests/test_readme.py README.md docs/project-status.html
git commit -m "docs: describe local monitoring workflow"
```

### Task 5: Publish and prove the deployment path

**Files:**

- Modify: none unless verification detects a defect

- [ ] **Step 1: Push commits**

Run: `git push origin main`

Expected: GitHub Actions starts CI.

- [ ] **Step 2: Verify CI, automatic deployment and health**

```bash
gh run list --repo hgbe-GH/Projet8-scoring-api --limit 1
render deploys list srv-daddn7oae00c739qdfq0 -o json
curl --fail --silent --show-error https://projet8-scoring-api.onrender.com/health
```

Expected: CI succeeds; Render displays a `new_commit` deployment after checks pass; health returns `status: ok`.

- [ ] **Step 3: Hand off evidence**

Provide the design, generated reports, README runbook, CI run and Render deployment links. State clearly that the drift output proves the monitoring mechanism, not real production drift, until a governed Project 6 reference is supplied.
