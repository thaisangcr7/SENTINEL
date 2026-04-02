# SENTINEL

A production-grade financial data pipeline that ingests live economic indicators from the [FRED API](https://fred.stlouisfed.org/), stores them in PostgreSQL, runs automated threshold checks, and exposes anomaly alerts via a REST API.

**Live API:** http://52.23.231.90:8000/docs

---

## What it does

Every time `POST /ingest` is called, SENTINEL:
1. Fetches the 24 most recent data points for 3 economic indicators from the FRED API
2. Saves them to PostgreSQL using an upsert (no duplicate rows)
3. Checks each series against configured thresholds
4. Fires alerts when a value change exceeds the threshold

**Tracked indicators:**
| Series | What it measures |
|--------|-----------------|
| `FEDFUNDS` | Federal funds interest rate |
| `CPIAUCSL` | Consumer Price Index (inflation) |
| `UNRATE` | Unemployment rate |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check — returns `{"status": "ok"}` |
| `GET` | `/metrics` | Last 100 observations from the database |
| `POST` | `/ingest` | Fetch live FRED data and store it |
| `POST` | `/thresholds` | Set an alert threshold for a series |
| `GET` | `/alerts` | List all fired alerts |

Full interactive docs: http://52.23.231.90:8000/docs

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI (Python) |
| Database | PostgreSQL 16 (Docker) |
| ORM | SQLAlchemy 2.0 |
| HTTP Client | httpx |
| Testing | pytest + pytest-mock |
| Infrastructure | Terraform (AWS EC2, t2.micro) |
| CI/CD | GitHub Actions |
| Server | Ubuntu 22.04 on AWS EC2 |

---

## Project Structure

```
SENTINEL/
├── app/
│   ├── main.py          # FastAPI app — 5 endpoints
│   ├── database.py      # PostgreSQL connection (SQLAlchemy engine + session)
│   ├── models.py        # Database tables: Observation, Threshold, Alert
│   ├── fred_client.py   # FRED API ETL pipeline (fetch → clean → upsert)
│   └── alert_checker.py # Anomaly detection (consecutive pair comparison)
├── tests/
│   └── test_api.py      # 10 pytest tests (all endpoints, mocked dependencies)
├── terraform/
│   ├── main.tf          # AWS resources: EC2, security group, key pair
│   ├── variables.tf     # Configurable values: region, instance type, SSH key
│   └── outputs.tf       # Post-apply outputs: public IP, SSH command
└── .github/
    └── workflows/
        └── ci-cd.yml    # CI: run tests. CD: deploy to EC2 if tests pass
```

---

## Running Locally

**Prerequisites:** Python 3.9+, Docker

```bash
# 1. Clone
git clone https://github.com/thaisangcr7/SENTINEL.git
cd SENTINEL

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Start PostgreSQL
docker run -d \
  --name sentinel-db \
  -e POSTGRES_USER=sentinel \
  -e POSTGRES_PASSWORD=sentinel_dev \
  -e POSTGRES_DB=sentinel \
  -p 5432:5432 \
  postgres:16-alpine

# 4. Create .env
echo "DATABASE_URL=postgresql://sentinel:sentinel_dev@localhost:5432/sentinel" > .env
echo "FRED_API_KEY=your_key_here" >> .env

# 5. Run
uvicorn app.main:app --reload
```

Get a free FRED API key at https://fred.stlouisfed.org/docs/api/api_key.html

---

## Running Tests

```bash
pytest tests/ -v
```

10 tests, all passing. Tests use mocks — no real database or FRED API needed.

---

## CI/CD Pipeline

Every push to `main`:
1. GitHub spins up a free Ubuntu runner
2. Installs dependencies and runs all 10 tests
3. If tests pass → SSHes into EC2 and deploys the new code automatically
4. If tests fail → stops. The live server stays on the working version.

---

## Infrastructure

Provisioned with Terraform:
- **EC2** — t2.micro (AWS free tier), Ubuntu 22.04, us-east-1
- **Security group** — ports 22 (SSH) and 8000 (API) open inbound
- **Key pair** — ED25519 SSH key, no passphrase (required for CI/CD automation)

To provision from scratch:
```bash
cd terraform
terraform init
terraform plan
terraform apply
```
