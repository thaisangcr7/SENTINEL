# models.py — Database Table Definitions
#
# Each class below = one table in PostgreSQL.
# Each attribute = one column in that table.
# SQLAlchemy reads these classes and creates/manages the real tables for you.
# You never write raw SQL for the schema — you write Python classes instead.

from __future__ import annotations  # Python 3.9 compat for Mapped[] syntax

from datetime import date, datetime
from sqlalchemy import String, Float, Date, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


# Observations — raw economic data from the FRED API
# Each row = one data point (e.g., FEDFUNDS on 2024-01-01 = 5.33)
class Observation(Base):
    __tablename__ = "observations"

    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[str] = mapped_column(String(50))
    date: Mapped[date] = mapped_column(Date)
    value: Mapped[float] = mapped_column(Float)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Unique on (series_id, date) — enables upsert so running /ingest twice won't duplicate rows
    __table_args__ = (
        UniqueConstraint("series_id", "date", name="uq_series_date"),
    )


# Thresholds — user-configured alert rules
# "For FEDFUNDS, alert me if it changes by more than 0.05 month-over-month"
class Threshold(Base):
    __tablename__ = "thresholds"

    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[str] = mapped_column(String(50), unique=True)
    max_change: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# Alerts — fired anomaly detections
# Created when alert_checker finds a change larger than the threshold
class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[str] = mapped_column(String(50))
    date: Mapped[date] = mapped_column(Date)
    value: Mapped[float] = mapped_column(Float)
    previous_value: Mapped[float] = mapped_column(Float)
    change: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
