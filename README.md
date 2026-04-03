# SENTINEL

A production-grade financial data pipeline that ingests live economic indicators from the [FRED API](https://fred.stlouisfed.org/), stores them in PostgreSQL, runs automated threshold checks, and exposes anomaly alerts via a REST API — deployed on AWS EC2 with Docker and a full CI/CD pipeline.

**Live API:** http://52.23.231.90:8000/docs

---

## What it does

Every time `POST /ingest` is called (manually or on a daily schedule), SENTINEL:
1. Fetches the 24 most recent data points for 3 economic indicators from the FRED API
2. Saves them to PostgreSQL using an upsert — no duplicate rows ever
3. Checks each series against configured thresholds
4. Fires an alert when a value change exceeds the threshold

**Tracked indicators:**
| Series | What it measures |
|--------|-----------------|
| `FEDFUNDS` | Federal funds interest rate |
| `CPIAUCSL` | Consumer Price Index (inflation) |
| `UNRATE` | Unemployment rate |

---

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/health` | None | Deep health check — verifies app and database are reachable |
| `GET` | `/metrics` | None | Last 100 observations from the database |
| `GET` | `/alerts` | None | List all fired alerts |
| `POST` | `/ingest` | API key | Fetch live FRED data and store it |
| `POST` | `/thresholds` | API key | Set an alert threshold for a series |

Full interactive docs: http://52.23.231.90:8000/docs

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI (Python 3.11) |
| Database | PostgreSQL 16 (Docker container) |
| ORM | SQLAlchemy 2.0 |
| Containerization | Docker + Docker Compose |
| Testing | pytest + pytest-mock (11 tests) |
| Logging | Python `logging` module (structured, timestamped) |
| Infrastructure | Terraform (AWS EC2 t2.micro, Ubuntu 22.04) |
| CI/CD | GitHub Actions (test → deploy → scheduled ingest) |

---

## Project Structure

```
SENTINEL/
├── app/
│   ├── main.py          # FastAPI app — 5 endpoints, auth, deep health check
│   ├── database.py      # PostgreSQL connection (SQLAlchemy engine + session)
│   ├── models.py        # Database tables: Observation, Threshold, Alert
│   ├── fred_client.py   # FRED API ETL pipeline (fetch → clean → upsert)
│   └── alert_checker.py # Anomaly detection (consecutive pair comparison)
├── tests/
│   └── test_api.py      # 11 pytest tests — all endpoints, all mocked
├── terraform/
│   ├── main.tf          # AWS resources: EC2, security group, key pair
│   ├── variables.tf     # Configurable values: region, instance type, SSH key
│   └── outputs.tf       # Post-apply outputs: public IP, SSH command
├── Dockerfile           # Python 3.11-slim image for the FastAPI app
├── docker-compose.yml   # Orchestrates app + db containers together
└── .github/
    └── workflows/
        └── ci-cd.yml    # CI: pytest. CD: deploy on push. Cron: daily ingest at 8am UTC
```

---

## Running Locally

**Prerequisites:** Docker (no Python needed locally)

```bash
# 1. Clone
git clone https://github.com/thaisangcr7/SENTINEL.git
cd SENTINEL

# 2. Create .env
cat > .env <<EOF
DATABASE_URL=postgresql://sentinel:sentinel_dev@db:5432/sentinel
FRED_API_KEY=your_key_here
API_KEY=your_api_key_here
POSTGRES_PASSWORD=sentinel_dev
EOF

# 3. Start both containers (app + postgres)
docker compose up -d --build

# 4. Create the database tables (first time only)
docker compose exec app python -c "from app.database import engine; from app.models import Base; Base.metadata.create_all(engine)"
```

App is now running at http://localhost:8000

Get a free FRED API key at https://fred.stlouisfed.org/docs/api/api_key.html

---

## Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

11 tests, all passing. Tests use mocks — no real database or FRED API needed.

---

## CI/CD Pipeline

Every push to `main`:
1. GitHub spins up a free Ubuntu runner
2. Installs dependencies and runs all 11 tests
3. If tests pass → SSHes into EC2, pulls the new code, and runs `docker compose up -d --no-deps app`
4. If tests fail → stops. The live server stays on the last working version.

Additionally, a **daily cron job** runs at 8am UTC to automatically call `POST /ingest` and keep the database fresh.

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
