<!--
GitHub About:
📡 Production-style economic data monitoring on AWS — ingest FRED data, detect anomalies, and serve alerts through FastAPI.

Suggested topics:
data-engineering, aws, fastapi, postgresql, terraform, fred-api, anomaly-detection, ci-cd, github-actions, python
-->

# 📡 SENTINEL

### Know when economic data starts behaving strangely.

Economic data changes constantly.

Most analysis projects stop at a notebook.

**SENTINEL goes further.**

It is a production-style financial data pipeline that pulls U.S. economic indicators from the [FRED API](https://fred.stlouisfed.org/), stores them in PostgreSQL, runs automated threshold checks, and exposes anomaly alerts through a FastAPI REST API.

The AWS environment is defined in Terraform, and deployments run through GitHub Actions.

> **Built to practice the parts notebooks skip: deployment, infrastructure, testing, CI/CD, and security.**

> **Not currently hosted.** SENTINEL ran on AWS EC2 for approximately five months. I took the instance down rather than continue paying to keep a portfolio demo online when nobody was querying it.
>
> The infrastructure is the artifact worth keeping: `terraform apply` from `terraform/` recreates the EC2 instance, security group, and key pair from code. To run it locally instead, `docker compose up` requires nothing from AWS.

---

## What it does

Every time `POST /ingest` is called — manually or through the scheduled workflow — SENTINEL:

1. Fetches the 24 most recent observations for three economic indicators from the FRED API
2. Saves them to PostgreSQL using an upsert, preventing duplicate rows
3. Checks each series against configured thresholds
4. Creates an alert when the value change exceeds the configured threshold

### Tracked indicators

| Series | What it measures |
|---|---|
| `FEDFUNDS` | Federal Funds Rate |
| `CPIAUCSL` | Consumer Price Index (inflation) |
| `UNRATE` | Unemployment Rate |

The goal is simple:

> **Turn raw economic observations into a small, reliable monitoring service.**

---

## Why I built it

A notebook can answer:

> "What happened to unemployment?"

A production system has to answer different questions:

- How does the data refresh automatically?
- Where is the history stored?
- What happens when ingestion runs twice?
- How is the API deployed?
- Can the infrastructure be recreated?
- What prevents broken code from reaching production?
- How should secrets and write endpoints be protected?

I built SENTINEL to work through those problems.

---

# Key results

| | |
|---|---:|
| Economic indicators monitored | **3** |
| Observations fetched per ingest | **24 per series** |
| Automated API tests | **11** |
| Cloud platform | **AWS EC2** |
| Infrastructure | **Terraform** |
| Deployment pipeline | **GitHub Actions** |
| Security issues found and fixed before launch | **6** |
| Live deployment period | **~5 months** |

---

# How SENTINEL works

```text
FRED API
   │
   ▼
Fetch latest observations
   │
   ▼
Clean + validate
   │
   ▼
PostgreSQL upsert
   │
   ▼
Threshold checks
   │
   ├── Normal
   │
   └── Threshold exceeded ──► Alert
                                 │
                                 ▼
                           FastAPI REST API
```

---

# 1. Ingest economic data

SENTINEL connects to the [FRED API](https://fred.stlouisfed.org/) and retrieves the latest observations for each configured indicator.

```text
FRED API
   ↓
Python ingestion service
   ↓
Clean / normalize
   ↓
PostgreSQL
```

An upsert is used when writing observations so running ingestion repeatedly does not create duplicate records.

This matters because automated pipelines retry.

---

# 2. Store the history

Observations are stored in PostgreSQL so the system can compare new values against previous observations.

That supports:

- historical queries
- change detection
- threshold checks
- alert generation
- API responses
- repeatable analysis

The API does not need to call FRED every time someone requests a result.

The data is collected first, stored, and then served from the database.

---

# 3. Detect unusual movements

SENTINEL compares consecutive observations against configurable thresholds.

Conceptually:

```text
Previous value
      +
Current value
      ↓
Calculate change
      ↓
Compare with threshold
      ↓
Normal / Alert
```

The goal is not to predict the economy.

It is to identify when an indicator moves enough to deserve attention.

---

# 4. Serve the results

FastAPI exposes the stored observations and alerts through REST endpoints.

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | None | Deep health check — verifies application and database connectivity |
| `GET` | `/metrics` | None | Returns the last 100 observations |
| `GET` | `/alerts` | None | Lists fired alerts |
| `POST` | `/ingest` | API key | Fetches current FRED data and stores it |
| `POST` | `/thresholds` | API key | Sets the alert threshold for a series |

Historical interactive API docs from the original deployment:

**http://52.23.231.90:8000/docs**

> The EC2 instance is no longer running, so this URL is retained as a record of the original deployment and is not expected to respond today.

---

# Production-style deployment

The most important part of SENTINEL is not the threshold logic.

It is the surrounding system.

## Infrastructure as code

The AWS environment is defined with **Terraform** rather than being manually assembled through the AWS console.

Terraform provisions:

- **EC2** — `t2.micro`, Ubuntu 22.04, `us-east-1`
- **Security group** — network access rules
- **Key pair** — ED25519 SSH key used by the deployment workflow

To provision the environment:

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

This makes the infrastructure version-controlled and reproducible.

---

# CI/CD

Every push to `main` runs the GitHub Actions pipeline:

```text
Push to main
      ↓
GitHub Actions
      ↓
Install dependencies
      ↓
Run 11 tests
      ↓
Tests pass?
   ┌───────┴───────┐
   │               │
  No              Yes
   │               │
   ▼               ▼
 Stop        Deploy to EC2
                   │
                   ▼
            Pull latest code
                   │
                   ▼
       Restart application container
```

If the tests fail, deployment stops and the live server stays on the last working version.

A scheduled GitHub Actions workflow also calls `POST /ingest` daily at **8:00 UTC** to refresh the database.

> **Treat deployment as part of the software, not a final manual step.**

---

# If you redeploy it, put it behind HTTPS

The original deployment served plain HTTP on the instance's public IP, which browsers mark as **Not secure**.

If SENTINEL goes live again, the deployment should use HTTPS.

## 0. Allocate a static address first

`main.tf` does not currently allocate an Elastic IP, so a freshly created EC2 instance receives a dynamic public address.

If the instance is stopped and started, that address can change. A DNS record would then point at the wrong server and certificate renewal could fail later.

Allocate and attach an Elastic IP before configuring DNS:

```bash
ALLOC=$(aws ec2 allocate-address --domain vpc --query AllocationId --output text)
aws ec2 associate-address --instance-id <instance-id> --allocation-id "$ALLOC"
```

> Attaching the Elastic IP replaces the instance's existing public address, so any old IP-based URL stops working at that point.
>
> Review current AWS pricing before redeploying because public IPv4 address pricing can change.

## 1. Configure DNS

In Cloudflare, create an `A` record such as:

```text
api.yourdomain.com → <elastic-ip>
```

Keep the Cloudflare proxy **off** initially (`DNS only`) so Let's Encrypt can reach the instance directly during certificate validation.

## 2. Open ports 80 and 443

Apply the Terraform configuration from `terraform/`.

Port 80 is used for the ACME challenge and HTTP-to-HTTPS redirect.

Port 443 serves HTTPS.

## 3. Enable HTTPS with Caddy

Run the included provisioning script:

```bash
ssh ubuntu@<instance-ip> 'sudo bash -s' < scripts/enable-https.sh
```

The script checks that DNS resolves to the instance, installs Caddy, proxies requests to the FastAPI application on `localhost:8000`, and obtains the TLS certificate.

It is safe to run more than once.

Once HTTPS is working, close public access to port `8000` in Terraform and apply again.

Uvicorn can remain bound to localhost while Caddy handles external traffic.

---

# Security review

Before considering the original deployment complete, I reviewed the application and infrastructure for security issues.

The review uncovered **6 vulnerabilities**, which I fixed before launch.

That process reinforced an important lesson:

> **Production engineering is not just making the system work. It is asking what should not be exposed.**

Areas reviewed included:

- API authentication
- secret handling
- exposed ports
- protected write endpoints
- deployment configuration
- failure behavior

---

# Architecture

```text
┌──────────────────────────────────────────────────────┐
│                     SENTINEL                         │
├──────────────────────────────────────────────────────┤
│                                                      │
│                    FRED API                          │
│                       │                              │
│                       ▼                              │
│                Ingestion Service                     │
│                       │                              │
│                       ▼                              │
│                 Clean + Validate                     │
│                       │                              │
│                       ▼                              │
│                   PostgreSQL                         │
│                       │                              │
│             ┌─────────┴─────────┐                    │
│             │                   │                    │
│             ▼                   ▼                    │
│      Threshold Checks       FastAPI API              │
│             │                   │                    │
│             ▼                   │                    │
│           Alerts ────────────────┘                    │
│                       │                              │
│                       ▼                              │
│                  API Consumer                        │
│                                                      │
├──────────────────────────────────────────────────────┤
│ AWS EC2 · Terraform · Docker Compose                 │
│ GitHub Actions · CI/CD · Scheduled Ingestion         │
└──────────────────────────────────────────────────────┘
```

---

# Tech stack

| Layer | Technology |
|---|---|
| API | FastAPI · Python 3.11 |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.0 |
| Containerization | Docker · Docker Compose |
| Testing | pytest · pytest-mock |
| Logging | Python `logging` |
| Infrastructure | Terraform · AWS EC2 |
| CI/CD | GitHub Actions |
| Data source | [FRED API](https://fred.stlouisfed.org/) |

---

# Project structure

```text
SENTINEL/
├── app/
│   ├── main.py          # FastAPI app — endpoints, auth, health check
│   ├── database.py      # SQLAlchemy engine + session
│   ├── models.py        # Observation, Threshold, Alert tables
│   ├── fred_client.py   # FRED ETL: fetch → clean → upsert
│   └── alert_checker.py # Consecutive-value threshold comparison
├── tests/
│   └── test_api.py      # 11 mocked API tests
├── terraform/
│   ├── main.tf          # EC2, security group, key pair
│   ├── variables.tf     # Region, instance type, SSH key
│   └── outputs.tf       # Public IP and SSH output
├── scripts/
│   └── enable-https.sh  # Caddy / HTTPS provisioning
├── Dockerfile
├── docker-compose.yml
└── .github/
    └── workflows/
        └── ci-cd.yml    # Test → deploy → scheduled ingest
```

---

# Run locally

**Prerequisite:** Docker. No local Python installation is required for the application containers.

## 1. Clone the repository

```bash
git clone https://github.com/thaisangcr7/SENTINEL.git
cd SENTINEL
```

## 2. Create `.env`

```bash
cat > .env <<EOF
DATABASE_URL=postgresql://sentinel:sentinel_dev@db:5432/sentinel
FRED_API_KEY=your_key_here
API_KEY=your_api_key_here
POSTGRES_PASSWORD=sentinel_dev
EOF
```

## 3. Start the application and PostgreSQL

```bash
docker compose up -d --build
```

## 4. Create the database tables

First run only:

```bash
docker compose exec app python -c "from app.database import engine; from app.models import Base; Base.metadata.create_all(engine)"
```

The API is now available at:

**http://localhost:8000**

Get a free FRED API key here:

**https://fred.stlouisfed.org/docs/api/api_key.html**

---

# Run the tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

**11 tests, all passing.**

The tests use mocks, so they do not require a live PostgreSQL database or real FRED API requests.

---

# Engineering decisions

## 1. Use upserts for ingestion

Automated workflows retry.

Running ingestion twice should not create duplicate observations.

## 2. Store data before serving it

The API should not depend on FRED being available for every read request.

Ingestion and serving are separate responsibilities.

## 3. Define infrastructure in code

Manual cloud configuration is difficult to reproduce.

Terraform makes the environment explicit and version-controlled.

## 4. Block deployment when tests fail

A successful push should not automatically mean a successful deployment.

The CI pipeline must pass first.

## 5. Keep the demo disposable

The EC2 instance is not the project.

The application code, infrastructure definition, deployment process, tests, and operational decisions are the reusable artifacts.

That is why the live server could be shut down without losing the project.

---

# What I wanted to learn

SENTINEL started as a data engineering project, but the bigger question became:

> **What happens after the analysis works?**

That led into:

- external API ingestion
- PostgreSQL data modeling
- idempotent writes
- backend APIs
- AWS deployment
- infrastructure as code
- CI/CD
- scheduled jobs
- testing
- API authentication
- application security
- operational reliability

The biggest lesson:

> **A calculation is only one part of a production system.**

The infrastructure, deployment process, security, testing, and failure behavior matter too.

---

# Project status

📡 **SENTINEL is not currently hosted.**

It ran on AWS EC2 for approximately five months before I intentionally shut the instance down to avoid paying for an idle portfolio demo.

The project remains fully reproducible through Docker for local development and Terraform for AWS infrastructure.
