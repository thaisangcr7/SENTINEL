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

from fastapi import FastAPI
from pydantic import BaseModel

from sqlalchemy import select
from app.database import SessionLocal
from app.models import Observation, Threshold, Alert

from app.fred_client import ingest_all
from app.alert_checker import check_alerts

app = FastAPI(title="SENTINEL", version="0.1.0")


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
@app.post("/ingest")
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
@app.post("/thresholds")
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
