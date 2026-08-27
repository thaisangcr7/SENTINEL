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

## HTTPS

The API is served over plain HTTP on the instance IP. To move it to
`https://api.sangthai.dev`, in this order:

0. **A static address first.** The instance currently has a *dynamic* public
   IP — no Elastic IP is allocated. Stop and start the instance and the address
   changes, which would leave the DNS record pointing at nothing and break
   certificate renewal. Allocate one and attach it before going further:

   ```bash
   ALLOC=$(aws ec2 allocate-address --domain vpc --query AllocationId --output text)
   aws ec2 associate-address --instance-id <instance-id> --allocation-id "$ALLOC"
   ```

   Note this *replaces* the current public address, so the existing
   `http://<old-ip>:8000` link stops working at that moment. An Elastic IP is
   free while attached to a running instance and billed only when left
   unattached.

1. **DNS** — in Cloudflare, add an `A` record `api` pointing at the Elastic IP,
   with the proxy **off** (grey cloud, "DNS only"). Let's Encrypt must reach
   the box directly to validate the domain; a proxied record answers on
   Cloudflare's addresses and validation fails.
2. **Ports** — `terraform apply` from `terraform/`. Ports 80 and 443 are
   declared in `main.tf`; 80 is needed only for the ACME challenge and the
   redirect to HTTPS.
3. **Caddy** — run the provisioning script against the box:

   ```bash
   ssh ubuntu@<instance-ip> 'sudo bash -s' < scripts/enable-https.sh
   ```

   It checks the DNS record resolves here before touching anything, installs
   Caddy, points it at the app on `localhost:8000`, and waits for the
   certificate. Safe to run twice.

Once that is serving, close port 8000 in `main.tf` and apply again — uvicorn
binds localhost and Caddy reaches it from inside the instance, so nothing
outside needs port 8000 any more.

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
