# main.py — The API layer. Everything starts here.
#
# This file defines all the HTTP endpoints (URLs) that clients call.
# When someone hits an endpoint, this file runs the right function.
#
# How the pieces connect:
# Architectural overview:
#   Client → main.py → fred_client.py → FRED API
#                ↓            ↓
#         alert_checker.py ← PostgreSQL
#
# Rule of thumb: GET endpoints = just read data. POST endpoints = do something / change data.
# Security rule: READ endpoints are public. WRITE endpoints require an API key.

import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from sqlalchemy import select
from app.database import SessionLocal
from app.models import Observation, Threshold, Alert

from app.fred_client import ingest_all
from app.alert_checker import check_alerts

app = FastAPI(title="SENTINEL", version="0.1.0")


# ── API Key Security ──────────────────────────────────────────────────────────
#
# Pattern: Fail Fast — crash at startup if the secret is missing.
# If API_KEY is not in the environment, the app refuses to start.
# This forces whoever deploys the app to set it — no silent misconfiguration.
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise RuntimeError("API_KEY is not set")

# Pattern: APIKeyHeader
# This tells FastAPI to look for a header named "X-API-Key" on every request.
# It also auto-documents the header in /docs as a lock icon.
# Setting auto_error=False means WE control the error message (not FastAPI).
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: str = Depends(api_key_header)):
    """Pattern: Dependency Function (a reusable security gate).

    FastAPI calls this function BEFORE running any endpoint that declares it.
    If the key is wrong or missing, we raise HTTPException — FastAPI stops
    the request immediately and returns 401 to the caller.
    The protected endpoint function never even runs.

    We add it to an endpoint like this:
        @app.post("/ingest", dependencies=[Depends(require_api_key)])

    Using 'dependencies=[...]' on the decorator (not a function param) means
    FastAPI runs the check but does not inject a return value — cleaner for
    "gate-only" checks like auth.
    """
    if key is None or key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# Health check — load balancers use this to know the server is alive
@app.get("/health")
def health_check():
    return {"status": "ok"}


# Return the 100 most recent observations (read-only)
@app.get("/metrics")
def get_metrics():
    db = SessionLocal()
    try:
        query = select(Observation).order_by(Observation.date.desc()).limit(100)
        results = db.execute(query).scalars().all()
        return [
            {
                "series_id": r.series_id,
                "date": str(r.date),
                "value": r.value,
                "fetched_at": str(r.fetched_at),
            }
            for r in results
        ]
    finally:
        db.close()


# Trigger the full pipeline: fetch from FRED → upsert → check alerts
# POST because it changes data. In production, a cron job calls this.
# Protected: requires X-API-Key header — prevents anyone from spamming the FRED API.
@app.post("/ingest", dependencies=[Depends(require_api_key)])
def run_ingestion():
    results = ingest_all()
    alerts = check_alerts()
    return {"ingested": results, "alerts_fired": alerts}


# Pattern: Pydantic Request Validation
# Define the expected shape of the JSON body as a class.
# FastAPI runs the check automatically — wrong field types get rejected
# with a 422 error before our function even runs.
class ThresholdRequest(BaseModel):
    series_id: str
    max_change: float


# Create or update an alert threshold (app-level upsert)
# Protected: requires X-API-Key header — prevents anyone from overwriting alert rules.
@app.post("/thresholds", dependencies=[Depends(require_api_key)])
def create_threshold(req: ThresholdRequest):
    db = SessionLocal()
    try:
        existing = db.execute(
            select(Threshold).where(Threshold.series_id == req.series_id)
        ).scalar_one_or_none()

        if existing:
            existing.max_change = req.max_change
        else:
            db.add(Threshold(series_id=req.series_id, max_change=req.max_change))

        db.commit()
        return {"series_id": req.series_id, "max_change": req.max_change}
    finally:
        db.close()


# List the 50 most recent fired alerts
@app.get("/alerts")
def get_alerts():
    db = SessionLocal()
    try:
        results = db.execute(
            select(Alert).order_by(Alert.created_at.desc()).limit(50)
        ).scalars().all()
        return [
            {
                "series_id": a.series_id,
                "date": str(a.date),
                "value": a.value,
                "previous_value": a.previous_value,
                "change": a.change,
                "created_at": str(a.created_at),
            }
            for a in results
        ]
    finally:
        db.close()
