# tests/test_api.py — API endpoint tests for SENTINEL
#
# These tests check that each endpoint returns the right response
# without needing a real database or the real FRED API.
#
# How testing without a real database works:
#   We use pytest-mock (mocker.patch) to replace the real database session
#   and real external calls with fake stand-ins that return controlled data.
#   This makes tests fast, reliable, and runnable without any infrastructure.
#
# Pattern: TestClient
#   FastAPI ships with a TestClient that lets us send fake HTTP requests
#   to the app and inspect the response — no server needs to be running.

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from datetime import date, datetime

from app.main import app

# TestClient wraps the FastAPI app so we can call it like a real HTTP server
client = TestClient(app)


# ── Test 1: GET /health ──────────────────────────────────────────────────────
# The simplest possible test — no database, no mocking needed.
# If this fails, the whole app is broken.
def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ── Test 2: GET /metrics returns a list ──────────────────────────────────────
# We mock SessionLocal so the test never touches a real database.
# The mock returns two fake Observation objects so we can check the shape
# of the JSON response without needing real data.
def test_get_metrics_returns_list(mocker):
    # Build two fake observation objects with the exact fields our endpoint reads
    fake_obs = MagicMock()
    fake_obs.series_id = "FEDFUNDS"
    fake_obs.date = date(2024, 1, 1)
    fake_obs.value = 5.33
    fake_obs.fetched_at = datetime(2024, 1, 2, 10, 0, 0)

    # Pattern: Mock the database session
    # We replace SessionLocal() with a fake that returns our fake data.
    # The real database is never opened.
    mock_db = MagicMock()
    mock_db.execute.return_value.scalars.return_value.all.return_value = [fake_obs]
    mocker.patch("app.main.SessionLocal", return_value=mock_db)

    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["series_id"] == "FEDFUNDS"
    assert data[0]["value"] == 5.33


# ── Test 3: GET /metrics returns empty list when no data ─────────────────────
def test_get_metrics_empty(mocker):
    mock_db = MagicMock()
    mock_db.execute.return_value.scalars.return_value.all.return_value = []
    mocker.patch("app.main.SessionLocal", return_value=mock_db)

    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.json() == []


# ── Test 4: POST /ingest calls ingest_all and check_alerts ───────────────────
# We don't test the actual ingestion logic here — that's fred_client's job.
# We just confirm that /ingest calls both functions and returns their results.
# Protected endpoint — we must include the API key header.
def test_ingest_calls_pipeline(mocker):
    mocker.patch("app.main.ingest_all", return_value={"FEDFUNDS": 24, "CPIAUCSL": 23, "UNRATE": 23})
    mocker.patch("app.main.check_alerts", return_value=[])

    response = client.post("/ingest", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    body = response.json()
    assert body["ingested"]["FEDFUNDS"] == 24
    assert body["alerts_fired"] == []


# ── Test 4b: POST /ingest returns 401 when API key is missing ─────────────────
# This verifies the security gate is actually working.
# No API key header → 401 Unauthorized. The pipeline never runs.
def test_ingest_rejected_without_api_key():
    response = client.post("/ingest")
    assert response.status_code == 401


# ── Test 5: POST /thresholds creates a new threshold ─────────────────────────
def test_create_threshold(mocker):
    mock_db = MagicMock()
    # scalar_one_or_none returns None → no existing threshold → we create a new one
    mock_db.execute.return_value.scalar_one_or_none.return_value = None
    mocker.patch("app.main.SessionLocal", return_value=mock_db)

    response = client.post("/thresholds", json={"series_id": "FEDFUNDS", "max_change": 0.05}, headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert response.json() == {"series_id": "FEDFUNDS", "max_change": 0.05}


# ── Test 6: POST /thresholds updates an existing threshold ───────────────────
# If a threshold already exists for that series, we update it — not duplicate it.
def test_update_existing_threshold(mocker):
    from app.models import Threshold

    existing = MagicMock(spec=Threshold)
    existing.max_change = 0.10

    mock_db = MagicMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = existing
    mocker.patch("app.main.SessionLocal", return_value=mock_db)

    response = client.post("/thresholds", json={"series_id": "FEDFUNDS", "max_change": 0.25}, headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    # The existing object's max_change should have been updated
    assert existing.max_change == 0.25


# ── Test 7: POST /thresholds rejects bad input ───────────────────────────────
# Pydantic should reject a request where max_change is a string, not a float.
# FastAPI returns 422 Unprocessable Entity automatically — no code needed on our side.
# Note: we include the API key so the auth check passes and Pydantic's check can run.
def test_create_threshold_invalid_body():
    response = client.post("/thresholds", json={"series_id": "FEDFUNDS", "max_change": "not-a-number"}, headers={"X-API-Key": "test-key"})
    assert response.status_code == 422


# ── Test 8: GET /alerts returns a list ───────────────────────────────────────
def test_get_alerts_returns_list(mocker):
    fake_alert = MagicMock()
    fake_alert.series_id = "FEDFUNDS"
    fake_alert.date = date(2024, 9, 1)
    fake_alert.value = 5.08
    fake_alert.previous_value = 5.33
    fake_alert.change = -0.25
    fake_alert.created_at = datetime(2024, 9, 2, 10, 0, 0)

    mock_db = MagicMock()
    mock_db.execute.return_value.scalars.return_value.all.return_value = [fake_alert]
    mocker.patch("app.main.SessionLocal", return_value=mock_db)

    response = client.get("/alerts")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["series_id"] == "FEDFUNDS"
    assert data[0]["change"] == -0.25


# ── Test 9: GET /alerts returns empty list when no alerts ────────────────────
def test_get_alerts_empty(mocker):
    mock_db = MagicMock()
    mock_db.execute.return_value.scalars.return_value.all.return_value = []
    mocker.patch("app.main.SessionLocal", return_value=mock_db)

    response = client.get("/alerts")
    assert response.status_code == 200
    assert response.json() == []


# ── Test 10: POST /ingest returns alert details when alerts fire ──────────────
# When the pipeline detects a large change, the response should include it.
def test_ingest_returns_fired_alerts(mocker):
    fired = [{
        "series_id": "FEDFUNDS",
        "date": "2024-09-01",
        "value": 5.08,
        "previous_value": 5.33,
        "change": -0.25,
    }]
    mocker.patch("app.main.ingest_all", return_value={"FEDFUNDS": 24})
    mocker.patch("app.main.check_alerts", return_value=fired)

    response = client.post("/ingest", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    body = response.json()
    assert len(body["alerts_fired"]) == 1
    assert body["alerts_fired"][0]["series_id"] == "FEDFUNDS"
    assert body["alerts_fired"][0]["change"] == -0.25
