# alert_checker.py — Checks if any recent data changes are bigger than expected
#
# After new data is ingested, this file scans it for unusual changes.
# For each series that has a threshold set, it looks at the last 24 months
# and compares each month to the one before it.
# If the change is bigger than allowed (in either direction), it saves an Alert.

from datetime import datetime
from sqlalchemy import select
from app.database import SessionLocal
from app.models import Observation, Threshold, Alert


def check_alerts() -> list[dict]:
    """Scan all thresholds against recent observations. Returns newly fired alerts."""
    db = SessionLocal()
    fired = []

    # Pattern: try/except/finally (Database Transaction)
    # try   → do the work, then save all new alerts at once
    # except → if anything fails, undo everything
    # finally → always close the session
    try:
        thresholds = db.execute(select(Threshold)).scalars().all()

        for threshold in thresholds:
            observations = db.execute(
                select(Observation)
                .where(Observation.series_id == threshold.series_id)
                .order_by(Observation.date.desc())
                .limit(24)
            ).scalars().all()

            if len(observations) < 2:
                continue

            # Pattern: Set for Deduplication
            # Load all dates that already have an alert into a Python set.
            # Checking "is this date in the set" is instant, and prevents firing the same alert twice.
            existing_alerts = db.execute(
                select(Alert.date)
                .where(Alert.series_id == threshold.series_id)
            ).scalars().all()
            existing_dates = set(existing_alerts)

            # Pattern: Consecutive Pair Comparison
            # observations[0] = newest month, [1] = month before, and so on.
            # Each step through the loop compares two adjacent months to measure the change.
            for i in range(len(observations) - 1):
                current = observations[i]
                previous = observations[i + 1]
                change = current.value - previous.value

                # Pattern: Absolute Value Check
                # abs() removes the sign, so +0.25 and -0.30 are both treated as "big changes".
                # Without abs(), a large drop would never trigger the alert.
                if abs(change) > threshold.max_change and current.date not in existing_dates:
                    alert = Alert(
                        series_id=threshold.series_id,
                        date=current.date,
                        value=current.value,
                        previous_value=previous.value,
                        change=round(change, 4),
                        created_at=datetime.utcnow(),
                    )
                    db.add(alert)
                    existing_dates.add(current.date)
                    fired.append({
                        "series_id": threshold.series_id,
                        "date": str(current.date),
                        "value": current.value,
                        "previous_value": previous.value,
                        "change": round(change, 4),
                    })

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return fired
