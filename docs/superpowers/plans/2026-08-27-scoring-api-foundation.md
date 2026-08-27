# Scoring API Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a test-covered FastAPI service that serves the Projet 6 scoring model, runs in Docker, and is checked and deployed by GitHub Actions.

**Architecture:** FastAPI creates one `ModelService` during application lifespan and reuses it for every request. `POST /predict` validates all 44 fields, makes a one-row pandas DataFrame for the serialized scikit-learn pipeline, writes a JSON-line event, and returns score, threshold, decision and model version.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, Uvicorn, pandas, scikit-learn, XGBoost, joblib, pytest, httpx, Docker, GitHub Actions.

---

## File map

| Path | Responsibility |
|---|---|
| `.gitignore` | Ignore virtual environments, secrets, logs and raw data. |
| `requirements.txt` | Runtime and test dependencies. |
| `src/scoring_api/schemas.py` | 44-field Pydantic contract and response schema. |
| `src/scoring_api/model_service.py` | Load joblib once and score requests. |
| `src/scoring_api/logging_service.py` | Structured production events. |
| `src/scoring_api/main.py` | Lifespan and HTTP routes. |
| `tests/` | Assets, contract, inference, logging and HTTP tests. |
| `Dockerfile` | Self-contained API image. |
| `.github/workflows/ci.yml` | CI, image smoke test and Hugging Face deployment. |

### Task 1: Add scaffold and model artefacts

**Files:** Create `.gitignore`, `requirements.txt`, `src/scoring_api/__init__.py`, `tests/__init__.py`, `tests/test_model_assets.py`, and copy `Projet6/models/matchers_option_a_model.joblib` plus `matchers_option_a_metadata.json` unchanged into `models/`.

- [ ] **Step 1: Write the failing test**

```python
import json
from pathlib import Path


def test_model_metadata_describes_serialised_champion() -> None:
    root = Path(__file__).resolve().parents[1]
    metadata = json.loads((root / "models/matchers_option_a_metadata.json").read_text())
    assert (root / "models/matchers_option_a_model.joblib").is_file()
    assert metadata["champion_name"] == "xgboost_search"
    assert metadata["feature_count"] == 44
    assert metadata["threshold_business_optimal"] == 0.06
```

- [ ] **Step 2: Verify red** — run `PYTHONPATH=src pytest tests/test_model_assets.py -v`; it must fail because the files do not yet exist.

- [ ] **Step 3: Add minimum configuration**

```text
# .gitignore
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.env
.env.*
logs/
data/raw/
data/interim/
data/processed/
mlruns/

# requirements.txt
fastapi==0.116.1
uvicorn[standard]==0.35.0
pandas==2.3.2
scikit-learn==1.7.1
xgboost==3.0.4
joblib==1.5.1
pytest==8.4.1
httpx==0.28.1
```

- [ ] **Step 4: Verify green and commit** — run `PYTHONPATH=src pytest tests/test_model_assets.py -v`, then `git add .gitignore requirements.txt src/scoring_api tests models && git commit -m "feat: add versioned scoring model contract"`.

### Task 2: Define and test the input contract

**Files:** Create `tests/conftest.py`, `tests/test_schemas.py`, and `src/scoring_api/schemas.py`.

- [ ] **Step 1: Write failing tests**

```python
import pytest
from pydantic import ValidationError
from scoring_api.schemas import PredictionRequest


def test_prediction_request_accepts_complete_payload(valid_payload: dict[str, object]) -> None:
    assert PredictionRequest.model_validate(valid_payload).client_effectif == valid_payload["client_effectif"]


def test_prediction_request_rejects_missing_required_feature(valid_payload: dict[str, object]) -> None:
    valid_payload.pop("heures_prevues")
    with pytest.raises(ValidationError, match="heures_prevues"):
        PredictionRequest.model_validate(valid_payload)


def test_prediction_request_rejects_text_for_numeric_feature(valid_payload: dict[str, object]) -> None:
    valid_payload["montant_demande_eur"] = "not-a-number"
    with pytest.raises(ValidationError, match="montant_demande_eur"):
        PredictionRequest.model_validate(valid_payload)


def test_prediction_request_rejects_negative_planned_hours(valid_payload: dict[str, object]) -> None:
    valid_payload["heures_prevues"] = -1
    with pytest.raises(ValidationError, match="heures_prevues"):
        PredictionRequest.model_validate(valid_payload)
```

- [ ] **Step 2: Verify red** — run `PYTHONPATH=src pytest tests/test_schemas.py -v`; expected failure: module `scoring_api.schemas` is missing.

- [ ] **Step 3: Implement** — create a complete synthetic `valid_payload` fixture using all 44 metadata fields. `PredictionRequest` uses `ConfigDict(extra="forbid", strict=True)` and direct fields in exact metadata order. It uses strict float for code/ratio fields, non-negative strict integers for prior-count fields, a positive strict integer for `client_rang_dossier`, positive strict floats for `heures_prevues`, `montant_demande_eur` and `taux_horaire_demande_eur`, and stripped non-empty strings for the 18 categorical fields. Add `PredictionResponse(risk_score, threshold, risk_flag, model_name, model_version)`.

- [ ] **Step 4: Verify green and commit** — run `PYTHONPATH=src pytest tests/test_schemas.py -v`; then `git add src/scoring_api/schemas.py tests/conftest.py tests/test_schemas.py && git commit -m "feat: validate scoring prediction inputs"`.

### Task 3: Load the pipeline once and score

**Files:** Create `tests/test_model_service.py` and `src/scoring_api/model_service.py`.

- [ ] **Step 1: Write failing tests**

```python
from pathlib import Path
from scoring_api.model_service import ModelService
from scoring_api.schemas import PredictionRequest


def test_model_service_scores_valid_request(valid_payload: dict[str, object]) -> None:
    root = Path(__file__).resolve().parents[1]
    service = ModelService.from_paths(root / "models/matchers_option_a_model.joblib", root / "models/matchers_option_a_metadata.json")
    result = service.predict(PredictionRequest.model_validate(valid_payload))
    assert 0 <= result.risk_score <= 1
    assert result.threshold == 0.06
    assert result.model_name == "xgboost_search"
```

- [ ] **Step 2: Verify red** — run `PYTHONPATH=src pytest tests/test_model_service.py -v`; expected missing-module failure.

- [ ] **Step 3: Implement** — a frozen `PredictionResult` dataclass and `ModelService.from_paths`. The factory calls `joblib.load` and parses JSON once. `predict` creates `pd.DataFrame([request.model_dump()])`, orders columns with `metadata["feature_columns"]`, uses `predict_proba(frame)[:, 1][0]`, and derives `risk_flag` from `threshold_business_optimal`. Add a test that monkeypatches `joblib.load`, scores twice with one service, and asserts one load.

- [ ] **Step 4: Verify green and commit** — run `PYTHONPATH=src pytest tests/test_model_service.py -v`; then `git add src/scoring_api/model_service.py tests/test_model_service.py && git commit -m "feat: load and score with champion model"`.

### Task 4: Add structured JSON-lines events

**Files:** Create `tests/test_logging_service.py` and `src/scoring_api/logging_service.py`.

- [ ] **Step 1: Write the failing test**

```python
import json
from scoring_api.logging_service import PredictionEventLogger


def test_event_logger_writes_features_score_and_latency(tmp_path) -> None:
    logger = PredictionEventLogger(tmp_path / "predictions.jsonl")
    logger.log_prediction({"heures_prevues": 21.0}, 0.18, True, 12.5, "2026-06-15")
    event = json.loads((tmp_path / "predictions.jsonl").read_text())
    assert event["event_type"] == "prediction"
    assert event["features"]["heures_prevues"] == 21.0
    assert event["duration_ms"] == 12.5
```

- [ ] **Step 2: Verify red** — run `PYTHONPATH=src pytest tests/test_logging_service.py -v`; expected missing-module failure.

- [ ] **Step 3: Implement** — `PredictionEventLogger` creates parent directories and appends UTF-8 JSON. Its successful event has UTC timestamp, event type, validated features, score, flag, latency, model version and `status: "success"`; it records no headers, IP addresses, credentials or unvalidated body.

- [ ] **Step 4: Verify green and commit** — run `PYTHONPATH=src pytest tests/test_logging_service.py -v`; then `git add src/scoring_api/logging_service.py tests/test_logging_service.py && git commit -m "feat: log scoring production events"`.

### Task 5: Implement HTTP routes

**Files:** Create `tests/test_api.py` and `src/scoring_api/main.py`.

- [ ] **Step 1: Write failing tests**

```python
from fastapi.testclient import TestClient
from scoring_api.main import app


def test_health_reports_ready_model() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_predict_returns_business_decision(valid_payload: dict[str, object]) -> None:
    with TestClient(app) as client:
        response = client.post("/predict", json=valid_payload)
    assert response.status_code == 200
    body = response.json()
    assert 0 <= body["risk_score"] <= 1
    assert body["risk_flag"] is (body["risk_score"] >= body["threshold"])
```

- [ ] **Step 2: Verify red** — run `PYTHONPATH=src pytest tests/test_api.py -v`; expected missing-module failure.

- [ ] **Step 3: Implement** — use FastAPI lifespan to create one service from `models/` and one logger at `logs/predictions.jsonl`; save both to `app.state`. `GET /health` returns state, model name and model version. `POST /predict` accepts `PredictionRequest`, measures `time.perf_counter`, calls the service once, logs the result, and returns `PredictionResponse`. Pydantic covers `422`; missing model gives opaque `503`; unexpected inference errors produce opaque `500` and an error event.

- [ ] **Step 4: Verify green and commit** — run `PYTHONPATH=src pytest -v`; then `git add src/scoring_api/main.py tests/test_api.py && git commit -m "feat: expose scoring prediction API"`.

### Task 6: Build and smoke-test the Docker image

**Files:** Create `.dockerignore`, `Dockerfile`, `tests/test_container_smoke.sh`, and `README.md`.

- [ ] **Step 1: Write failing smoke test** — a Bash script must `docker build -t projet8-scoring-api:test .`, run it on port 8000, retry `curl --fail --silent http://127.0.0.1:8000/health` 20 times, and clean up the named container with `trap`.

- [ ] **Step 2: Verify red** — run `bash tests/test_container_smoke.sh`; expected failure because `Dockerfile` is absent.

- [ ] **Step 3: Implement** — Python 3.12 slim image, matching the MLflow-recorded model environment, `/app` workdir, `PYTHONPATH=/app/src`, copied requirements then `pip install --no-cache-dir`, source and model copies, port 8000, and `uvicorn scoring_api.main:app --host 0.0.0.0 --port 8000`. Docker ignore excludes Git, data, docs, tests, logs, venv and notebooks.

- [ ] **Step 4: Verify green and commit** — run `bash tests/test_container_smoke.sh && PYTHONPATH=src pytest -v`; then `git add Dockerfile .dockerignore README.md tests/test_container_smoke.sh && git commit -m "build: containerize scoring API"`.

### Task 7: Automate CI/CD

**Files:** Create `.github/workflows/ci.yml`, `tests/test_ci_workflow.py`; modify `README.md`.

- [ ] **Step 1: Write failing workflow check** — test that reads `.github/workflows/ci.yml` and asserts it contains `PYTHONPATH=src pytest -v`, `bash tests/test_container_smoke.sh`, `HF_TOKEN` and `HF_SPACE_ID`.

- [ ] **Step 2: Verify red** — run `PYTHONPATH=src pytest tests/test_ci_workflow.py -v`; expected `FileNotFoundError`.

- [ ] **Step 3: Implement** — workflow triggers on pull requests and pushes to main. Job `test` uses checkout, Python 3.11, requirements and pytest. Job `build-and-smoke-test` needs test and runs the Bash test. Job `deploy-hugging-face` needs smoke test and runs only on a main push when both secrets are configured. It installs `huggingface_hub` and uploads the Docker Space using secret environment variables only. README explains setting `HF_TOKEN` and `HF_SPACE_ID` in GitHub Actions secrets.

- [ ] **Step 4: Verify green and commit** — run `PYTHONPATH=src pytest tests/test_ci_workflow.py -v && PYTHONPATH=src pytest -v`; then `git add .github/workflows/ci.yml tests/test_ci_workflow.py README.md && git commit -m "ci: add test build and deployment workflow"`.

### Task 8: Publish the remote

**Files:** Modify `README.md` only if a remote URL needs adding.

- [ ] **Step 1: Verify authentication** — run `gh auth status`; require a GitHub account authorized to create public repositories.

- [ ] **Step 2: Publish** — run `gh repo create Projet8-scoring-api --public --source=. --remote=origin --push`.

- [ ] **Step 3: Confirm publication** — run `git remote -v` and `git ls-remote --heads origin main`; `origin` must be the public GitHub URL and main must be present.

## Plan self-review

- **Coverage:** Tasks 1–5 cover the model, inputs, errors, one-time loading and logging; Task 6 covers Docker; Task 7 covers test/build/deploy; Task 8 covers public Git history.
- **Scope:** Monitoring and data-drift analysis will be planned after this service creates representative log data.
- **Safety:** No raw Project6 data, logs, credentials or GitHub/Hugging Face tokens are committed.
