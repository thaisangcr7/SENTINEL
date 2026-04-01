# database.py — How SENTINEL connects to PostgreSQL
#
# Before any endpoint can read or write data, it needs an open line to the database.
# This file opens that line and exports 3 things every other file uses:
#
#   engine       — the actual connection to PostgreSQL
#   SessionLocal — call SessionLocal() to start a database "workspace" for one request
#   Base         — every table class (Observation, Threshold, Alert) inherits from this
#                  so SQLAlchemy knows they are database tables, not regular Python classes

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Load secrets from .env — keeps passwords out of source code
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

# Pattern: Connection Pool
# create_engine() connects to PostgreSQL and keeps a pool of connections ready.
# Reusing connections is much faster than opening a new one on every request.
engine = create_engine(DATABASE_URL)

# Pattern: Session Factory
# sessionmaker() gives us a class (SessionLocal) we call to start a new database session.
# Each session is one isolated workspace — open it, do your work, then close it.
# Think of it like a shopping cart: you fill it, then check out or cancel.
SessionLocal = sessionmaker(bind=engine)


# Pattern: Declarative Base
# All table classes (Observation, Threshold, Alert) inherit from Base.
# This tells SQLAlchemy they represent real database tables, not regular Python classes.
class Base(DeclarativeBase):
    pass
