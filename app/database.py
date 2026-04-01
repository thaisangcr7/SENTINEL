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

# create_engine() opens the connection to PostgreSQL using the URL from .env
# It keeps a pool of connections ready so we don't reconnect on every request
engine = create_engine(DATABASE_URL)

# sessionmaker() creates a class (SessionLocal) that we use to start database sessions.
# Every time you call db = SessionLocal(), you get a fresh workspace to run queries.
# Think of it like opening a new tab in a spreadsheet — isolated, then close it when done.
SessionLocal = sessionmaker(bind=engine)


# All table classes (Observation, Threshold, Alert) inherit from Base.
# SQLAlchemy uses this to know which Python classes map to actual database tables.
class Base(DeclarativeBase):
    pass
