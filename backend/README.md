# Sentra-X: Backend Service & Database Layer

**Asynchronous REST API Gateway, SQLAlchemy 2.0 ORM, and PostgreSQL 16 Persistence Engine**

---

## 1. Overview

The `backend/` package hosts the core application logic and data boundary of **Sentra-X**:
- **FastAPI Application Gateway:** Exposes 21 REST API endpoints supporting OpenAPI 3.1 documentation, asynchronous route handling, and RFC 7519 JWT Bearer authentication.
- **Relational Persistence Layer:** Powered by **PostgreSQL 16** and **SQLAlchemy 2.0** mapped models, enforcing 13 database domain `CHECK` constraints, partial indexes for sub-50ms exemplar retrieval, and hardware-grade PL/pgSQL immutability triggers.
- **Deterministic Rules & Guardrails:** Intercepts LLM evaluations to enforce deterministic safety floors (`rule.level ≥ 12`), uncertainty-aware abstentions (`confidence < 0.60`), dot-notation citation verification, and prompt-injection defense.
- **Driver Topology:** Unified on **Psycopg (v3)** — synchronous engine (`postgresql+psycopg://`) for CLI scripts/Alembic migrations, and asynchronous engine (`postgresql+psycopg_async://`) for FastAPI request pipelines.

---

## 2. Directory Structure

```
backend/
├── alembic/                      # Database migration scripts
│   ├── versions/
│   │   ├── 0001_initial_schema.py             # Initial schema DDL, B-tree indexes, immutability trigger
│   │   ├── 0002_align_srs_v14.py              # SRS v1.4 column alignments & audit constraint update
│   │   ├── 0003_add_srs_check_constraints.py  # 13 formal database-level CHECK constraints
│   │   ├── 0004_add_system_configurations.py  # Table 8: system_configurations table for persistence
│   │   └── 0005_abr_audit_hardening.py        # Nullability relaxations, correlation indexes & trigger
│   ├── env.py                    # Alembic migration runner supporting target metadata
│   └── script.py.mako            # Migration template
├── alembic.ini                   # Alembic configuration file
├── app/                          # Main application package
│   ├── models/                   # SQLAlchemy 2.0 Declarative Models (All 8 Tables)
│   │   ├── user.py               # User table (Identity, salted bcrypt, RBAC role)
│   │   ├── asset.py              # Asset registry table (agent_id, hostname, criticality_tier)
│   │   ├── alert.py              # Alert table (Wazuh telemetry, rule metadata, status)
│   │   ├── evidence_pack.py      # EvidencePack table (sanitized telemetry, citation keys)
│   │   ├── ai_assessment.py      # AIAssessment table (verdicts, severities, guardrail flags)
│   │   ├── audit.py              # AnalystDecisionAudit table (immutable append-only audit log)
│   │   ├── exemplar.py           # FeedbackExemplar table (dynamic few-shot calibration store)
│   │   ├── system_configuration.py # Persistent multi-worker system configuration model
│   │   └── base.py               # Shared DeclarativeBase metadata
│   ├── routers/                  # FastAPI API Routers
│   │   ├── auth.py               # /api/v1/auth (login, session /me, token issuance)
│   │   ├── alerts.py             # /api/v1/alerts (queue, count badges, alert detail, decisions)
│   │   ├── analytics.py          # /api/v1/analytics (KPI metrics, override trends, CSV audit export)
│   │   ├── governance.py         # /api/v1/governance (exemplar management, asset registry)
│   │   ├── evaluation.py         # /api/v1/evaluation (adversarial benchmark runner & report)
│   │   └── admin.py              # /api/v1/admin (system config parameters & user admin)
│   ├── schemas/                  # Pydantic v2 Request & Response Serialization Schemas
│   ├── services/                 # Core Business & Inference Logic
│   │   ├── rules_engine.py       # Deterministic safety floor & abstention logic
│   │   ├── prompt_sanitizer.py   # Delimiter sanitization & injection pattern detection
│   │   ├── evidence_assembler.py # EvidencePack compilation & dot-notation key extraction
│   │   ├── llm_adapter.py        # Google Gemini / Anthropic Claude inference adapters
│   │   └── evaluation_runner.py  # 30-payload adversarial benchmark executor
│   ├── auth.py                   # JWT token encode/decode and RBAC security dependencies
│   ├── config.py                 # Application settings loaded from .env
│   ├── database.py               # Sync and async database session factories
│   ├── demo_seed.json            # Authoritative SRS v1.4 SOC baseline telemetry dataset
│   ├── main.py                   # FastAPI application initialization & middleware
│   ├── seed_data.py              # Deterministic database seeder (populating all 8 tables)
│   └── utils.py                  # Parsing utilities (e.g., parse_uuid)
├── scripts/                      # Database Administration Scripts
│   ├── reset_db.py               # Wipes all tables and reseeds demo_seed.json
│   └── wipe_db.py                # Wipes operational telemetry while preserving schema & users
├── tests/                        # Verification & Test Harnesses
│   ├── test_api_endpoints.py     # Comprehensive 20+ endpoint REST integration suite
│   ├── test_db_schema.py         # Direct PostgreSQL engine CHECK constraint validation suite
│   ├── test_rules_engine.py      # Unit tests for guardrail thresholds and safety floors
│   ├── test_prompt_sanitizer.py  # Unit tests for prompt injection neutralization
│   └── test_evidence_assembler.py# Unit tests for evidence compilation and citation extraction
├── requirements.txt              # Pinned Python dependencies (including google-genai)
└── .env.example                  # Environment configuration template
```

---

## 3. Setup & Installation

### Prerequisites
- Python `3.11` or higher
- PostgreSQL `16.x` running on `localhost:5432` with database `sentrax` owned by user `sentrax`

### Step 1: Virtual Environment
```bash
python -m venv .venv

# Windows PowerShell:
.\.venv\Scripts\Activate.ps1

# Linux / macOS:
# source .venv/bin/activate
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Ensure database credentials match your environment:
```env
DATABASE_URL=postgresql+psycopg://sentrax:sentrax@localhost:5432/sentrax
DATABASE_URL_ASYNC=postgresql+psycopg_async://sentrax:sentrax@localhost:5432/sentrax
JWT_SECRET_KEY=sentrax-super-secret-jwt-key-2026
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480
```

---

## 4. Database Migrations & Seeding

```bash
# Apply all Alembic migrations to create tables, indexes, and triggers:
alembic upgrade head

# Seed baseline demonstration SOC telemetry:
python app/seed_data.py

# Alternatively, run the idempotent full reset script:
python scripts/reset_db.py
```

---

## 5. Running the Backend Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- **API Base URL:** `http://localhost:8000`
- **Interactive Swagger Documentation:** `http://localhost:8000/docs`
- **ReDoc Technical Specification:** `http://localhost:8000/redoc`

---

## 6. Automated Testing & Verification

The normal Uvicorn and Compose startup paths start the triage worker in the API
process. For a local smoke test, use a disposable PostgreSQL database with the
migrations applied and set `LLM_PROVIDER=mock` in `backend/.env` or the process
environment. `TRIAGE_ENABLED=false` disables the worker. Run one API process for
this deployment. The pending-row sweep recovers queued work after a restart.

Replay an alert from `tests/fixtures/replay/ac1_100.jsonl` into the disposable
database while the API runs. A qualifying alert should reach
`AWAITING_ANALYST` and have an evidence pack and an assessment. To verify
recovery, ingest a fresh alert while the worker is disabled, then restart with
the worker enabled and check that the pending alert reaches the same state.

Benchmark report reads return `null` until an admin explicitly runs the
evaluation. Exports return 404 until a report exists. Each run is held in the
API process memory. Mock results identify themselves as dry runs, and provider
errors make a run inconclusive.

```bash
# 1. Execute the comprehensive 16-endpoint REST integration test suite:
python tests/test_api_endpoints.py

# 2. Verify all 13 PostgreSQL CHECK constraints directly against the live database:
pytest tests/test_db_schema.py

# 3. Run individual core service unit tests:
pytest tests/test_rules_engine.py
pytest tests/test_prompt_sanitizer.py
pytest tests/test_evidence_assembler.py
```

---

## 7. Evaluator Credentials

| Username | Role | Password |
| :--- | :---: | :--- |
| `analyst_01` | Analyst | `sentrax2026` |
| `teamlead_mercer` | TeamLead | `sentrax2026` |
| `admin_sys` | Admin | `sentrax2026` |
