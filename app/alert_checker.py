from datetime import datetime
from sqlalchemy import select
from app.database import SessionLocal
from app.models import Observation, Threshold, Alert


def check_alerts() -> list[dict]:
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

            existing_alerts = db.execute(
                select(Alert.date)
                .where(Alert.series_id == threshold.series_id)
            ).scalars().all()
            existing_dates = set(existing_alerts)

            for i in range(len(observations) - 1):
                current = observations[i]
                previous = observations[i + 1]
                change = current.value - previous.value

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
