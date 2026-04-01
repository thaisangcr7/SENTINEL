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

            # Load dates that already have alerts into a Python set.
            # We check this before creating new alerts so we never fire the same alert twice.
            existing_alerts = db.execute(
                select(Alert.date)
                .where(Alert.series_id == threshold.series_id)
            ).scalars().all()
            existing_dates = set(existing_alerts)

            # Compare consecutive pairs: [i] = current month, [i+1] = previous month
            for i in range(len(observations) - 1):
                current = observations[i]
                previous = observations[i + 1]
                change = current.value - previous.value

                # abs() = absolute value, so we catch both UP spikes and DOWN drops.
                # Example: threshold is 0.05. Change of +0.25 triggers it. Change of -0.30 also triggers it.
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
