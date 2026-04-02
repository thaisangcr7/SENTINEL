# tests/conftest.py — Test environment setup
#
# pytest automatically discovers and loads this file BEFORE any test file runs.
# This is the right place to set environment variables that app modules need
# at import time — variables that would normally come from a real .env file.
#
# Why we need this file:
#   When tests import "from app.main import app", Python runs main.py immediately.
#   main.py reads DATABASE_URL, API_KEY (and fred_client.py reads FRED_API_KEY)
#   at the TOP of the file. If those env vars are not set, the app raises
#   RuntimeError — before any test even runs.
#
#   By setting them here with os.environ.setdefault(), we guarantee they are
#   always present during tests — on any machine, in CI, or locally.
#
# setdefault() vs os.environ["KEY"] = "value":
#   os.environ.setdefault() only sets the variable if it is NOT already set.
#   This means if someone runs tests with a REAL env var, it won't be overwritten.
#   If no env var exists (blank runner), our safe test value is used.

import os

# Pattern: Test Environment Defaults
# These values are fake — they never connect to a real database or real API.
# Tests mock all real calls, so these just need to exist and be non-empty.
os.environ.setdefault("DATABASE_URL", "postgresql://fake:fake@localhost:5432/fake")
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("FRED_API_KEY", "fake-fred-key")
