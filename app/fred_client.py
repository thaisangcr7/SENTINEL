# fred_client.py — Fetches economic data from the FRED API and saves it to PostgreSQL
#
# This is the data collection step. It does three things in order:
#   1. Ask the FRED API for the latest numbers (e.g., the federal funds rate)
#   2. Clean up the data (skip blanks, convert strings to floats)
#   3. Save to the database — if a row already exists, update it instead of adding a duplicate
#
# This whole pattern is called ETL (Extract → Transform → Load) in data engineering.

import os
import httpx
from datetime import datetime
from sqlalchemy.dialects.postgresql import insert  # PostgreSQL-specific upsert syntax
from app.database import SessionLocal
from app.models import Observation


FRED_API_KEY = os.getenv("FRED_API_KEY")
# Pattern: Fail Fast — same pattern as DATABASE_URL in database.py
# If the key is missing, crash immediately at startup with a clear message.
# Better to fail at boot than to fail silently when someone calls /ingest.
if not FRED_API_KEY:
    raise RuntimeError("FRED_API_KEY is not set")

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# FEDFUNDS = Fed interest rate, CPIAUCSL = inflation, UNRATE = unemployment
SERIES_IDS = ["FEDFUNDS", "CPIAUCSL", "UNRATE"]


def fetch_series(series_id: str) -> list[dict]:
    """EXTRACT — call FRED API, return raw observation dicts (24 most recent months)."""
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 24,
    }
    response = httpx.get(FRED_BASE_URL, params=params)
    response.raise_for_status()
    return response.json()["observations"]


def ingest_series(series_id: str) -> int:
    """TRANSFORM + LOAD — fetch one series, upsert into PostgreSQL. Returns row count."""
    observations = fetch_series(series_id)
    db = SessionLocal()
    count = 0

    # Pattern: try/except/finally (Database Transaction)
    # try   → do all the work, then commit (save all changes at once)
    # except → if anything fails, rollback (undo ALL changes — no partial saves)
    # finally → ALWAYS close the session, even if an error happened
    try:
        for obs in observations:
            if obs["value"] == ".": # FRED uses "." for missing data — skip it
                continue

            # Pattern: Upsert (INSERT + ON CONFLICT UPDATE)
            # Try to insert a new row. If a row with this (series_id + date) already exists,
            # update it instead of creating a duplicate.
            # This means you can run /ingest every day safely — no copies pile up.
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
    """Ingest all three FRED series. Returns {series_id: row_count}."""
    results = {}
    for series_id in SERIES_IDS:
        results[series_id] = ingest_series(series_id)
    return results
