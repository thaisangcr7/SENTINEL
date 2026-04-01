from fastapi import FastAPI

from sqlalchemy import select
from app.database import SessionLocal
from app.models import Observation

from app.fred_client import ingest_all

app = FastAPI(title="SENTINEL", version="0.1.0")

@app.get("/health")
def health_check():
    return {"status": "ok"}

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


@app.post("/ingest")
def run_ingestion():
    results = ingest_all()
    return {"ingested": results}
