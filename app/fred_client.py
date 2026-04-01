import os
import httpx
from datetime import datetime
from sqlalchemy.dialects.postgresql import insert
from app.database import SessionLocal
from app.models import Observation


FRED_API_KEY = os.getenv("FRED_API_KEY")
FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

SERIES_IDS = ["FEDFUNDS", "CPIAUCSL", "UNRATE"]


def fetch_series(series_id: str) -> list[dict]:
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 24,
    }
    response = httpx.get(FRED_BASE_URL, params=params)
    response.raise_for_status()
    data = response.json()
    return data["observations"]


def ingest_series(series_id: str) -> int:
    observations = fetch_series(series_id)
    db = SessionLocal()
    count = 0
    try:
        for obs in observations:
            if obs["value"] == ".":
                continue

            stmt = insert(Observation).values(
                series_id=series_id,
                date=obs["date"],
                value=float(obs["value"]),
                fetched_at=datetime.utcnow(),
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_series_date",
                set_={"value": float(obs["value"]), "fetched_at": datetime.utcnow()},
            )
            db.execute(stmt)
            count += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return count


def ingest_all() -> dict:
    results = {}
    for series_id in SERIES_IDS:
        results[series_id] = ingest_series(series_id)
    return results
