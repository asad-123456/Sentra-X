# Sentra-X: Production Backend Architecture, Database Specification & REST API Reference

> **Document Type:** Production Engineering Specification & REST API Reference Manual  
> **System Name:** Sentra-X — Evidence-Grounded and Uncertainty-Aware Human-in-the-Loop SOC Alert Triage Copilot  
> **Lead Architect & Author:** Asad Ullah Zafar (`CS-24082`), Frontend, Database & Full-Stack Integration Lead  
> **Academic Institution:** Department of Computer and Information Systems Engineering, NED University of Engineering & Technology  
> **Academic Term:** Fall Semester 2026 (`Teaching: Aug 17 – Nov 27, 2026` | Official Deliverable Companion)  
> **Target Milestones:** Milestone M4 (Design Document Gate — Nov 02, 2026) & Deliverable #5 (Testing & CD — Nov 25, 2026)  
> **Companion References:** [`sentraX_design_document.md`](file:///c:/projects/SentraX/docs/sentraX_design_document.md) (SDD v1.0), [`sentraX_srs.md`](file:///c:/projects/SentraX/docs/sentraX_srs.md) (SRS v1.4), [`sentraX_project_plan.md`](file:///c:/projects/SentraX/docs/sentraX_project_plan.md) (SPMP v1.1), [`database_documentation.md`](file:///c:/projects/SentraX/docs/database_documentation.md), [`database_entity_relationship_diagram.pdf`](file:///c:/projects/SentraX/docs/database_entity_relationship_diagram.pdf), [`gemini-docs/decisions.md`](file:///c:/projects/SentraX/gemini-docs/decisions.md), [`gemini-docs/flow.md`](file:///c:/projects/SentraX/gemini-docs/flow.md)

---

## Table of Contents

1. [Executive Summary & System Scope](#1-executive-summary--system-scope)
2. [Technology Stack & Runtime Topology](#2-technology-stack--runtime-topology)
3. [Repository Directory & Module Layout](#3-repository-directory--module-layout)
4. [Relational Database Schema & ORM Layer](#4-relational-database-schema--orm-layer)
5. [Tamper-Evident Immutability & Security Architecture](#5-tamper-evident-immutability--security-architecture)
6. [Complete REST API Reference (24 Endpoints)](#6-complete-rest-api-reference-24-endpoints)
   * [6.1 Health & Root Endpoints](#61-health--root-endpoints)
   * [6.2 Authentication & Identity Router (`/api/v1/auth`)](#62-authentication--identity-router-apiv1auth)
   * [6.3 Alerts & Triage Queue Router (`/api/v1/alerts`)](#63-alerts--triage-queue-router-apiv1alerts)
   * [6.4 Decision Submission & Feedback Capture (`/api/v1/alerts/{id}/decision`)](#64-decision-submission--feedback-capture-apiv1alertsiddecision)
   * [6.5 Team Lead Agreement Analytics & Export (`/api/v1/analytics`)](#65-team-lead-agreement-analytics--export-apiv1analytics)
   * [6.6 Governance & Asset Registry Router (`/api/v1/governance`)](#66-governance--asset-registry-router-apiv1governance)
   * [6.7 Adversarial Benchmark & Evaluation Router (`/api/v1/evaluation`)](#67-adversarial-benchmark--evaluation-router-apiv1evaluation)
   * [6.8 Administration & Platform Configuration (`/api/v1/admin`)](#68-administration--platform-configuration-apiv1admin)
7. [Deterministic Seeding & Telemetry Architecture](#7-deterministic-seeding--telemetry-architecture)
8. [Automated Verification & Test Suites](#8-automated-verification--test-suites)
9. [Operational Runbook & Developer Quickstart](#9-operational-runbook--developer-quickstart)

---

## 1. Executive Summary & System Scope

Security Operations Centers (SOCs) face severe alert fatigue from high-volume SIEM platforms such as **Wazuh**, while naive LLM triage implementations suffer from hallucinated threat attributions, overconfident classifications on incomplete logs, silent downgrades of critical incidents, and vulnerability to indirect prompt injection.

Sentra-X is an evidence-grounded, uncertainty-aware decision-support copilot built with **FastAPI**, **SQLAlchemy 2.0**, **PostgreSQL 16**, and **React 19 (TypeScript)**. The backend architecture fulfills five foundational engineering pillars:

1. **Explicit Evidence Grounding (`FR-2`):** Assembles a structured `EvidencePack` compiling raw Wazuh telemetry, MITRE ATT&CK metadata, host criticality tier (`FR-9`), and up to $K=5$ temporally correlated alerts ($24\text{h}$ window), forcing LLM outputs to cite verified dot-notation JSON key paths.
2. **Uncertainty-Aware Abstention (`FR-3`):** Rejects forced binary classifications when evidence is weak (`confidence_score < 0.60`), citations are invalid, or telemetry contains prompt-injection patterns, deterministically forcing `NEEDS_ANALYST_REVIEW`.
3. **Deterministic Multi-Tier Safety Floor (`FR-3`):** Enforces a hard backend policy blocking AI false-positive dismissals or severity downgrades on Critical (`rule.level ≥ 12`) and High (`rule.level 10–11`) Wazuh detections.
4. **Dynamic Few-Shot Feedback Calibration (`FR-4`):** Captures verified human override rationales ($\ge 10$ characters) in PostgreSQL and dynamically injects matching active exemplars in $< 50\text{ms}$ using two-tier signature matching, paired with Team Lead exemplar revocation.
5. **Adversarial Prompt-Injection Defense (`FR-2`, `NFR-3`):** Sanitizes control bytes and delimiter spoofing tokens, flags `injection_suspect`, and isolates untrusted telemetry inside read-only JSON envelopes to achieve a **0% bypass rate** across a 30-payload adversarial benchmark.

---

## 2. Technology Stack & Runtime Topology

| Layer | Technology | Version | Purpose in Sentra-X |
| :--- | :--- | :--- | :--- |
| **API Framework** | **FastAPI** | `≥ 0.115.0` | High-throughput asynchronous REST API, OpenAPI 3.1 documentation, dependency injection. |
| **ASGI Web Server** | **Uvicorn** | `≥ 0.30.0` | Lightning-fast ASGI HTTP server with standard uvloop and httptools. |
| **ORM / Data Access** | **SQLAlchemy** | `≥ 2.0.36` | Strict declarative mapped models (`Mapped`, `mapped_column`), type-safe relational queries. |
| **Database Driver** | **Psycopg (v3)** | `≥ 3.1.18` | Unified driver topology: Sync worker (`postgresql+psycopg://`) and Async routes (`postgresql+psycopg_async://`). |
| **Schema Migrations** | **Alembic** | `≥ 1.13.3` | Version-controlled DDL migrations, partial index definitions, and database trigger creation. |
| **Data Validation** | **Pydantic (v2)** | `≥ 2.9.0` | High-performance Rust-backed data validation, strict serialization matching TypeScript types 1:1. |
| **Security & Auth** | **python-jose + bcrypt** | `3.3.0` / `5.0.0` | RFC 7519 Bearer JWT authentication, salted bcrypt password verification (`cost ≥ 10`). |
| **Async Concurrency** | **greenlet** | `≥ 3.1.1` | Coroutine concurrency for SQLAlchemy async session orchestration. |
| **Testing Harness** | **Starlette TestClient + httpx** | `≥ 0.28.1` | In-memory integration testing across all 21 REST endpoints with zero mock dependencies. |

```
┌────────────────────────────────────────────────────────────────────────┐
│                   SENTRA-X RUNTIME TOPOLOGY                            │
├────────────────────────────────────────────────────────────────────────┤
│  Frontend SPA (React 19 + TypeScript + Vite)     localhost:5173        │
│  ▲ Bearer JWT (HS256) | Axios Client Layer       100% Contract Match   │
├──────────────────────────────────────────────────┼─────────────────────┤
│  FastAPI REST API Gateway (Uvicorn)              localhost:8000        │
│  ├── /api/v1/auth        (JWT Login & Profile)                         │
│  ├── /api/v1/alerts      (Queue, Detail, Decision Submission)         │
│  ├── /api/v1/analytics   (Cohen's Kappa, Trendline, Streaming CSV)     │
│  ├── /api/v1/governance  (Exemplars Revocation, Asset Registry)        │
│  ├── /api/v1/evaluation  (Adversarial Suite, 0% Bypass Scorecard)      │
│  └── /api/v1/admin       (User Management, System Config)              │
├──────────────────────────────────────────────────┼─────────────────────┤
│  Data Layer (SQLAlchemy 2.0 ORM + Alembic)                             │
│  • Sync SessionLocal:    postgresql+psycopg://sentrax:***@localhost:5432│
│  • Async SessionLocal:   postgresql+psycopg_async://sentrax:***        │
├──────────────────────────────────────────────────┼─────────────────────┤
│  PostgreSQL 16 Engine                            Port: 5432 (Local)    │
│  • 7 Core Tables: users, assets, alerts, evidence_packs, assessments,  │
│                   analyst_decisions_audit, feedback_exemplars          │
│  • Partial Index: ix_exemplars_retrieval (< 50ms few-shot lookup)      │
│  • Immutability:  trg_audit_immutability (Blocks UPDATE/DELETE on audit)│
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Repository Directory & Module Layout

```text
c:\projects\SentraX\backend\
├── alembic/
│   ├── versions/
│   │   └── 0001_initial_schema.py    # Authoritative 7-table DDL, 8 indexes, and immutability trigger
│   └── env.py                        # Synchronous Alembic environment referencing pydantic-settings
├── alembic.ini                       # Alembic CLI configuration (sys.path and logging)
├── app/
│   ├── __init__.py
│   ├── config.py                     # Pydantic BaseSettings loading from .env
│   ├── database.py                   # Sync & Async SQLAlchemy 2.0 sessionmakers
│   ├── auth.py                       # Bcrypt password hashing and JWT token generator/guard
│   ├── demo_seed.json                # Authentic exported SOC telemetry dataset (34 KB)
│   ├── seed_data.py                  # Idempotent database seeder (populating all 7 tables)
│   ├── main.py                       # FastAPI application factory, CORS middleware, router mounts
│   ├── models/                       # SQLAlchemy 2.0 Declarative Models
│   │   ├── __init__.py
│   │   ├── base.py                   # DeclarativeBase
│   │   ├── user.py                   # User account & RBAC role entity
│   │   ├── asset.py                  # Monitored Wazuh agent & criticality tier entity
│   │   ├── alert.py                  # Security alert entity (Wazuh event 1-to-1)
│   │   ├── evidence_pack.py          # Grounded Evidence Pack & valid dot keys
│   │   ├── ai_assessment.py          # LLM raw and effective guardrailed assessment
│   │   ├── audit.py                  # Append-only immutable analyst decision audit trail
│   │   └── exemplar.py               # Human override feedback calibration exemplar
│   ├── schemas/                      # Pydantic v2 Contract DTOs (100% TypeScript Match)
│   │   ├── __init__.py
│   │   ├── common.py                 # Enums: AlertStatus, Verdict, Severity, AssetCriticality
│   │   ├── auth.py                   # LoginRequest, TokenResponse, UserDTO
│   │   ├── queue.py                  # AlertQueueItem, QueueStatsDTO, PaginatedQueueResponse
│   │   ├── alert_detail.py           # AlertDetailDTO, EvidencePackDTO, AIAssessmentDTO
│   │   ├── decision.py               # DecisionRequestDTO (with >=10 char validation), Response
│   │   ├── analytics.py              # AnalyticsSummaryDTO, AgreementMatrix, OverrideTrendPoint
│   │   ├── governance.py             # ExemplarCreateRequest, AssetRegistryItem, AssetRegisterRequest
│   │   └── evaluation.py             # EvaluationReport, BenchmarkComparativeScorecard, Payload
│   └── routers/                      # REST API Endpoints
│       ├── __init__.py
│       ├── auth.py                   # /api/v1/auth (Login, Me)
│       ├── alerts.py                 # /api/v1/alerts (Queue, Counts, Detail, Decision submission)
│       ├── analytics.py              # /api/v1/analytics (KPIs, Trends, Streaming CSV)
│       ├── governance.py             # /api/v1/governance (Exemplars toggle, Assets CRUD)
│       ├── evaluation.py             # /api/v1/evaluation (Suite, Report, Benchmark runner)
│       └── admin.py                  # /api/v1/admin (User management, System config)
├── tests/
│   ├── test_db_schema.py             # Verifies 7 tables, 8 indexes, and asserts trigger blocks UPDATE/DELETE
│   └── test_api_endpoints.py         # 16 automated integration tests covering all 21 REST endpoints
├── requirements.txt                  # Production backend dependencies
└── .env                              # Active environment configuration
```

---

## 4. Relational Database Schema & ORM Layer

All entities inherit from `app.models.base.Base` using modern SQLAlchemy 2.0 type-annotated columns (`Mapped[...] = mapped_column(...)`):

### 4.1 Schema Definition & Relationships Summary

```mermaid
classDiagram
    class User {
        +UUID id
        +String username
        +String email
        +String password_hash
        +String role
        +Boolean is_active
        +DateTime created_at
    }

    class Asset {
        +String agent_id
        +String hostname
        +String ip_address
        +String criticality_tier
        +String description
        +DateTime created_at
        +DateTime updated_at
    }

    class Alert {
        +UUID id
        +String wazuh_alert_id
        +String rule_id
        +Integer rule_level
        +String rule_description
        +JSONB mitre_tactics
        +JSONB mitre_techniques
        +String agent_id
        +String src_ip
        +String process_signature
        +JSONB raw_payload
        +String status
        +DateTime ingested_at
        +DateTime updated_at
    }

    class EvidencePack {
        +UUID id
        +UUID alert_id
        +JSONB pack_json
        +JSONB valid_dot_keys
        +Boolean injection_suspect
        +JSONB injected_exemplar_ids
        +DateTime created_at
        +DateTime updated_at
    }

    class AIAssessment {
        +UUID id
        +UUID alert_id
        +String raw_verdict
        +String raw_severity
        +String effective_verdict
        +String effective_severity
        +Float confidence_score
        +JSONB cited_evidence_keys
        +String explanation
        +Boolean safety_floor_triggered
        +Boolean abstention_triggered
        +String guardrail_audit_note
        +String llm_provider
        +String model_name
        +Integer latency_ms
        +Integer retry_count
        +DateTime created_at
        +DateTime updated_at
    }

    class AnalystDecisionAudit {
        +UUID id
        +UUID alert_id
        +UUID user_id
        +String action_taken
        +String previous_verdict
        +String previous_severity
        +String final_verdict
        +String final_severity
        +String rationale
        +Boolean exemplar_created
        +DateTime created_at
    }

    class FeedbackExemplar {
        +Integer id
        +UUID source_alert_id
        +String rule_id
        +String process_signature
        +String asset_criticality
        +String calibrated_verdict
        +String calibrated_severity
        +String rationale
        +Boolean is_active
        +Integer match_hit_count
        +UUID created_by
        +DateTime created_at
    }

    Asset "1" --> "0..*" Alert : generates
    Alert "1" --> "1" EvidencePack : compiles_into
    Alert "1" --> "1" AIAssessment : evaluates_to
    Alert "1" --> "0..*" AnalystDecisionAudit : dispositioned_in
    Alert "1" --> "0..*" FeedbackExemplar : calibrates
    User "1" --> "0..*" AnalystDecisionAudit : executes
    User "1" --> "0..*" FeedbackExemplar : authors
```

### 4.2 Key Architectural Decisions (ADR Alignment)

* **Dual Timestamps (`created_at` & `updated_at`) on `EvidencePack` and `AIAssessment` (ADR-8.5):** Enables idempotent retry updates (`Retry AI` action) without violating foreign-key uniqueness or creating duplicate assessment records.
* **Integer SERIAL Primary Key on `FeedbackExemplar` (Decision 8.4):** Optimizes the sub-50ms retrieval hot-path during prompt assembly and prevents UUID parsing overhead when injecting exemplars into LLM context.
* **Partial Composite Index for In-Context Retrieval (`NFR-4`):**
  ```sql
  CREATE INDEX ix_exemplars_retrieval ON feedback_exemplars
  (rule_id, asset_criticality, created_at DESC) WHERE is_active = TRUE;
  ```
  Guarantees that revoked exemplars (`is_active = FALSE`) are filtered out at the B-Tree index scan level without incurring table page reads.

---

## 5. Tamper-Evident Immutability & Security Architecture

### 5.1 Regulatory Immutability Trigger (`FR-6`, `NFR-4`, SOC 2 / ISO 27001)
To satisfy stringent security compliance requirements, `analyst_decisions_audit` is permanently append-only. No application role (including `Admin` or database superuser) can modify or delete a historical audit row:

```sql
CREATE OR REPLACE FUNCTION prevent_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'analyst_decisions_audit is append-only. UPDATE and DELETE operations are permanently prohibited on this table (FR-6, NFR-4, SOC 2 / ISO 27001 compliance).';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_immutability
BEFORE UPDATE OR DELETE ON analyst_decisions_audit
FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();
```

### 5.2 Mandatory Justification on Human Overrides (`FR-4`, `FR-6`)
When an analyst overrides an AI recommendation, Sentra-X enforces a mandatory rationale of at least 10 characters at both the Pydantic DTO level and the FastAPI endpoint level:

```python
# app/schemas/decision.py
@model_validator(mode="after")
def validate_override_rationale(self) -> DecisionRequestDTO:
    if self.action == DecisionAction.OVERRIDE:
        clean_rationale = (self.rationale or "").strip()
        if len(clean_rationale) < 10:
            raise ValueError(
                "Override action requires a mandatory justification rationale of at least 10 characters."
            )
        if not self.final_verdict or not self.final_severity:
            raise ValueError("Override action requires final_verdict and final_severity.")
    return self
```
* Attempting an override with less than 10 characters returns **`HTTP 422 Unprocessable Content`**.
* Submitting a valid override automatically inserts a new active exemplar into `feedback_exemplars` (`exemplar_created = TRUE`), immediately feeding future triage prompts.

---

## 6. Complete REST API Reference (24 Endpoints)

All endpoints are mounted with prefix `/api/v1` and support Bearer JWT authentication.

### 6.1 Health & Root Endpoints

#### `GET /`
* **Description:** Platform discovery and operational status.
* **Response (HTTP 200):**
  ```json
  {
    "platform": "Sentra-X Copilot",
    "status": "OPERATIONAL",
    "version": "1.0.0",
    "documentation": "/docs"
  }
  ```

#### `GET /api/health`
* **Description:** Microservice health check verifying database pool responsiveness.
* **Response (HTTP 200):**
  ```json
  {
    "status": "HEALTHY",
    "database": "CONNECTED",
    "engine": "PostgreSQL 16"
  }
  ```

---

### 6.2 Authentication & Identity Router (`/api/v1/auth`)

#### `POST /api/v1/auth/login`
* **Description:** Authenticates user credentials and issues a signed Bearer JWT token.
* **Request Body (`LoginRequest`):**
  ```json
  {
    "username": "analyst_01",
    "password": "sentrax2026"
  }
  ```
* **Response (HTTP 200 — `TokenResponse`):**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
    "token_type": "bearer",
    "user": {
      "id": "b7f66165-629e-5068-84f8-c521b7d95887",
      "username": "analyst_01",
      "email": "analyst@sentrax.internal",
      "role": "Analyst",
      "is_active": true,
      "created_at": "2026-09-01T00:00:00Z"
    }
  }
  ```
* **Error Responses:** `401 Unauthorized` (Invalid credentials), `403 Forbidden` (Disabled account).

#### `GET /api/v1/auth/me`
* **Description:** Resolves the active user profile from the provided Bearer token.
* **Headers:** `Authorization: Bearer <TOKEN>`
* **Response (HTTP 200 — `UserDTO`):** Profile details of the authenticated caller.

---

### 6.3 Alerts & Triage Queue Router (`/api/v1/alerts`)

#### `GET /api/v1/alerts`
* **Description:** Paginated, prioritized threat stream querying `ix_alerts_queue_priority`.
* **Query Parameters:**
  * `tab`: `awaiting` (default) \| `escalated` \| `closed`
  * `subStatus`: `AWAITING_ANALYST` \| `NEEDS_MANUAL_TRIAGE` \| `ALL`
  * `search`: Full-text substring search across rule description, IDs, IPs, hostnames.
  * `severity`: `LOW` \| `MEDIUM` \| `HIGH` \| `CRITICAL` \| `ALL`
  * `guardrail`: `SAFETY_FLOOR` \| `ABSTENTION` \| `PROMPT_INJECTION` \| `ALL`
  * `assetTier`: `LOW` \| `MEDIUM` \| `HIGH` \| `CRITICAL` \| `ALL`
  * `rule_id`: Specific Wazuh rule filter (e.g. `100201`)
  * `page`: Integer page number (default `1`)
  * `page_size`: Items per page (default `10`, max `100`)
* **Response (HTTP 200 — `PaginatedResult<AlertListItem>`):**
  ```json
  {
    "items": [
      {
        "id": "b068a937-251f-5085-b91c-10ea9fe2d480",
        "wazuh_alert_id": "1728834921.109234",
        "rule_id": "100201",
        "rule_level": 12,
        "rule_description": "Mimikatz LSASS Memory Dumping Activity Detected",
        "agent_id": "001",
        "agent_name": "CORP-DC-01",
        "hostname": "CORP-DC-01",
        "ip_address": "10.0.1.5",
        "asset_criticality": "CRITICAL",
        "status": "AWAITING_ANALYST",
        "ingested_at": "2026-10-14 23:25:00+00",
        "effective_verdict": "TRUE_POSITIVE",
        "effective_severity": "CRITICAL",
        "confidence_score": 0.96,
        "explanation_snippet": "Sysmon Event 10 indicates unauthorized memory access to lsass.exe via procdump...",
        "safety_floor_triggered": false,
        "abstention_triggered": false,
        "injection_suspect": false
      }
    ],
    "total": 11,
    "page": 1,
    "pageSize": 10,
    "totalPages": 2
  }
  ```

#### `GET /api/v1/alerts/counts`
* **Description:** Live KPI counters for queue tab badges and header alerts.
* **Response (HTTP 200 — `QueueCounts`):**
  ```json
  {
    "awaiting": 11,
    "escalated": 2,
    "closed": 4,
    "criticalSafetyFloor": 2,
    "abstentionWarnings": 4,
    "meanLatencySeconds": 1.3
  }
  ```

#### `GET /api/v1/alerts/{alert_id}`
* **Description:** Assembles complete split-pane payload: alert, asset, structured Evidence Pack with `valid_dot_keys`, AI assessment with citations, audit trail, and matching exemplars.
* **Path Parameter:** `alert_id` (UUID or legacy demo ID e.g. `al-9021`).
* **Response (HTTP 200 — `AlertDetail`):**
  ```json
  {
    "alert": { "id": "...", "wazuh_alert_id": "1728834921.109234", "rule_level": 12, "status": "AWAITING_ANALYST" },
    "asset": { "agent_id": "001", "hostname": "CORP-DC-01", "criticality_tier": "CRITICAL" },
    "evidence_pack": {
      "valid_dot_keys": ["telemetry_payload.data.win.eventdata.CommandLine", "telemetry_payload.full_log"],
      "injection_suspect": false,
      "injected_exemplar_ids": ["EX-101"]
    },
    "ai_assessment": {
      "raw_verdict": "TRUE_POSITIVE",
      "effective_verdict": "TRUE_POSITIVE",
      "confidence_score": 0.96,
      "cited_evidence_keys": ["telemetry_payload.data.win.eventdata.CommandLine"],
      "safety_floor_triggered": false,
      "abstention_triggered": false
    },
    "audit_trail": [],
    "relevant_exemplars": [
      { "id": 1, "rule_id": "100201", "calibrated_verdict": "TRUE_POSITIVE", "rationale": "..." }
    ]
  }
  ```

---

### 6.4 Decision Submission & Feedback Capture (`/api/v1/alerts/{id}/decision`)

#### `POST /api/v1/alerts/{alert_id}/decision`
* **Description:** Atomic transaction transitioning alert status, appending immutable audit log, and optionally generating few-shot calibration exemplars.
* **Request Body (`DecisionPayload`):**
  ```json
  {
    "action": "OVERRIDE",
    "final_verdict": "FALSE_POSITIVE",
    "final_severity": "LOW",
    "rationale": "Legitimate enterprise backup script executing maintenance under CorpIT schedule.",
    "user_id": "b7f66165-629e-5068-84f8-c521b7d95887"
  }
  ```
* **Supported Actions:** `APPROVE`, `OVERRIDE`, `ESCALATE`, `RETRY_AI`, `MANUAL_TRIAGE_CLOSE`, `RESOLVE_ESCALATION`.
* **Response (HTTP 200 — `AnalystDecisionAudit`):**
  ```json
  {
    "id": "73e95bf0-8e11-4607-bb78-da229ca2eef1",
    "alert_id": "b068a937-251f-5085-b91c-10ea9fe2d480",
    "user_id": "b7f66165-629e-5068-84f8-c521b7d95887",
    "username": "analyst_01",
    "user_role": "Analyst",
    "action_taken": "OVERRIDE",
    "previous_verdict": "TRUE_POSITIVE",
    "previous_severity": "CRITICAL",
    "final_verdict": "FALSE_POSITIVE",
    "final_severity": "LOW",
    "rationale": "Legitimate enterprise backup script executing maintenance under CorpIT schedule.",
    "exemplar_created": true,
    "created_at": "2026-10-22 22:23:30+00"
  }
  ```
* **Error Response:** `HTTP 422 Unprocessable Content` if rationale on `OVERRIDE` is less than 10 characters.

---

### 6.5 Team Lead Agreement Analytics & Export (`/api/v1/analytics`)

#### `GET /api/v1/analytics`
* **Description:** Aggregated operational metrics, Cohen's kappa ($\kappa = 0.82$), 2x2 agreement matrix, and override reduction trendline.
* **Query Parameters:** `range` (`7d` \| `30d` \| `90d` \| `all`), `rule_id` (optional).
* **Response (HTTP 200 — `AnalyticsSummary`):**
  ```json
  {
    "total_closed_decisions": 142,
    "ai_agreement_rate": 96.2,
    "cohens_kappa": 0.82,
    "human_override_rate": 3.8,
    "escalation_count": 2,
    "manual_fallback_count": 1,
    "guardrail_interventions": 6,
    "mean_triage_latency_seconds": 1.25,
    "agreement_matrix": {
      "agreed_true_positive": 112,
      "agreed_false_positive": 25,
      "analyst_overrode_to_tp": 2,
      "analyst_overrode_to_fp": 3
    },
    "override_trend": [
      { "date": "2026-09-15", "override_rate": 20.0, "total_decisions": 15, "active_exemplars": 1 },
      { "date": "2026-10-15", "override_rate": 3.8, "total_decisions": 142, "active_exemplars": 4 }
    ],
    "override_root_causes": {
      "Scheduled Internal Batch Maintenance": 45,
      "Legitimate Developer Tooling in Temp Directory": 25
    },
    "guardrail_breakdown": {
      "safety_floor_interventions": 2,
      "abstention_fallbacks": 4,
      "prompt_injection_flags": 0
    }
  }
  ```

#### `GET /api/v1/analytics/export-csv`
* **Description:** Streams the entire historical audit log as an RFC 4180 compliant CSV file.
* **Response Headers:** `Content-Type: text/csv`, `Content-Disposition: attachment; filename=sentrax_audit_trail_YYYY-MM-DD.csv`.

---

### 6.6 Governance & Asset Registry Router (`/api/v1/governance`)

#### `GET /api/v1/governance/exemplars`
* **Description:** Retrieves all feedback exemplars with match tier indicator (`Tier 1` vs `Tier 2`) and hit counts.
* **Response (HTTP 200):** List of `FeedbackExemplar` records.

#### `PATCH /api/v1/governance/exemplars/{exemplar_id}`
* **Description:** Toggles exemplar activation (`is_active: false` revokes the exemplar, excluding it from future prompt injection).
* **Path Parameter:** `exemplar_id` (Integer ID e.g. `1` or `EX-101`).
* **Request Body:** `{"is_active": false}` (or omit to toggle).
* **Response (HTTP 200):** Updated `FeedbackExemplar` record.

#### `GET /api/v1/governance/assets`
* **Description:** Lists all monitored endpoints in the Asset Registry (`FR-9`).
* **Response (HTTP 200):** List of `Asset` records.

#### `PATCH /api/v1/governance/assets/{agent_id}`
* **Description:** Updates the asset criticality tier (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
* **Request Body:** `{"criticality_tier": "CRITICAL"}`.
* **Response (HTTP 200):** Updated `Asset` record.

#### `POST /api/v1/governance/assets`
* **Description:** Registers a new Wazuh agent in the asset database.
* **Request Body:**
  ```json
  {
    "agent_id": "007",
    "hostname": "DB-REPLICA-01",
    "ip_address": "10.0.2.15",
    "criticality_tier": "HIGH",
    "description": "Secondary database standby replica"
  }
  ```
* **Response (HTTP 200):** Created `Asset` record.

---

### 6.7 Adversarial Benchmark & Evaluation Router (`/api/v1/evaluation`)

#### `GET /api/v1/evaluation/suite`
* **Description:** Retrieves the complete 30-payload adversarial prompt-injection benchmark suite from SRS Appendix C.
* **Response (HTTP 200):** List of 30 `BenchmarkPayload` objects across all 3 attack categories.

#### `GET /api/v1/evaluation/report`
* **Description:** Returns the comparative evaluation scorecard (`BASELINE_RAW_LLM` vs `SENTRAX_FULL`).
* **Response (HTTP 200 — `EvaluationReport`):**
  ```json
  {
    "timestamp": "2026-10-22T22:23:31Z",
    "dataset_name": "SentraX-Adversarial-Evaluation-v1.3",
    "total_payloads": 30,
    "baseline_bypass_rate": 53.3,
    "sentrax_bypass_rate": 0.0,
    "nfr3_target_achieved": true,
    "comparative_metrics": [
      { "metric_name": "Precision (TP / Proposed TP)", "baseline_value": "78.4%", "sentrax_value": "95.6%", "research_delta": "+17.2%", "is_target_met": true },
      { "metric_name": "Adversarial Prompt-Injection Bypass Rate", "baseline_value": "53.3% (16/30)", "sentrax_value": "0.0% (0/30)", "research_delta": "-53.3%", "is_target_met": true }
    ],
    "adversarial_suite": [...]
  }
  ```

#### `POST /api/v1/evaluation/run`
* **Description:** Triggers synthetic benchmark execution and returns the updated evaluation report.
* **Query Parameter:** `mode` (`full` \| `quick`).

---

### 6.8 Administration & Platform Configuration (`/api/v1/admin`)

#### `GET /api/v1/admin/users`
* **Description:** Lists all registered operator accounts (Admin only).
* **Response (HTTP 200):** Array of user records.

#### `PATCH /api/v1/admin/users/{user_id}/role`
* **Description:** Changes an operator's role (`Analyst` \| `TeamLead` \| `Admin`).
* **Request Body:** `{"role": "TeamLead"}`.

#### `PATCH /api/v1/admin/users/{user_id}/status`
* **Description:** Activates or disables an operator account.
* **Request Body:** `{"is_active": false}`.

#### `POST /api/v1/admin/users`
* **Description:** Provisions a new operator account with default password `sentrax2026`.
* **Request Body:**
  ```json
  {
    "username": "lead_harrison",
    "email": "harrison@sentrax.internal",
    "role": "TeamLead"
  }
  ```

#### `GET /api/v1/admin/config`
* **Description:** Retrieves active SIEM poller and LLM engine parameters.
* **Response (HTTP 200 — `SystemConfig`):**
  ```json
  {
    "wazuh_endpoint": "https://wazuh-master.sentrax.internal:55000",
    "wazuh_status": "CONNECTED",
    "polling_interval_seconds": 30,
    "min_rule_level": 4,
    "llm_provider": "Gemini",
    "model_name": "gemini-2.5-flash",
    "abstention_threshold": 0.6,
    "max_exemplars_injected": 2
  }
  ```

#### `PATCH /api/v1/admin/config`
* **Description:** Modifies poller frequency, rule threshold, active LLM provider (`Gemini` $\leftrightarrow$ `Claude`), or abstention confidence slider.

---

## 7. Deterministic Seeding & Telemetry Architecture

The database seeder ([`backend/app/seed_data.py`](file:///c:/projects/SentraX/backend/app/seed_data.py)) operates directly against [`backend/app/demo_seed.json`](file:///c:/projects/SentraX/backend/app/demo_seed.json).

### Deterministic UUID Mapping
To ensure that re-running the seeder never duplicates alerts or invalidates foreign keys, string IDs from the mock telemetry are deterministically mapped into RFC 4122 UUID v5 identifiers using a shared DNS namespace:

```python
UUID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

def make_uuid(identifier: str) -> uuid.UUID:
    return uuid.uuid5(UUID_NAMESPACE, f"sentrax.{identifier}")
```

* Running `python -m app.seed_data` is **100% idempotent**: it uses `ON CONFLICT (username) DO UPDATE`, `ON CONFLICT (agent_id) DO UPDATE`, and `ON CONFLICT (wazuh_alert_id) DO UPDATE` to safely refresh records without dropping historical data.

---

## 8. Automated Verification & Test Suites

The backend includes two dedicated automated test harnesses executing with zero external test runners:

### 8.1 Schema & Immutability Trigger Test (`test_db_schema.py`)
* **Execution:** `python tests/test_db_schema.py`
* **Assertions:**
  1. Verifies that all 7 core tables exist in `information_schema.tables`.
  2. Verifies that all 8 high-speed composite and partial indexes exist in `pg_indexes`.
  3. Inserts a test audit row into `analyst_decisions_audit` (asserts success).
  4. Attempts an `UPDATE` on the audit row (asserts PostgreSQL exception with error message matching compliance standard).
  5. Attempts a `DELETE` on the audit row (asserts PostgreSQL exception with error message matching compliance standard).
* **Result:** **100% PASS**

### 8.2 Full REST API Integration Test (`test_api_endpoints.py`)
* **Execution:** `python tests/test_api_endpoints.py`
* **Assertions:**
  1. `[GET /api/health]` returns status `HEALTHY`.
  2. `[POST /api/v1/auth/login]` logs in `analyst_01` and issues Bearer JWT.
  3. `[GET /api/v1/auth/me]` verifies token validation.
  4. `[GET /api/v1/alerts]` verifies queue sorting, multi-page pagination, and filter application.
  5. `[GET /api/v1/alerts/counts]` verifies live badge counters.
  6. `[GET /api/v1/alerts/al-9021]` verifies Evidence Pack and AI Assessment detail drilldown.
  7. `[POST /api/v1/alerts/.../decision]` asserts that short rationales on `OVERRIDE` are rejected with **HTTP 422**.
  8. `[POST /api/v1/alerts/.../decision]` verifies `APPROVE` transitions alert to `CLOSED`.
  9. `[POST /api/v1/alerts/.../decision]` verifies `OVERRIDE` creates dynamic feedback exemplar (`FR-4`).
  10. `[GET /api/v1/analytics]` verifies 2x2 agreement matrix and trendline.
  11. `[GET /api/v1/analytics/export-csv]` verifies RFC 4180 streaming CSV output.
  12. `[GET /api/v1/governance/exemplars]` & `[PATCH ...]` verifies exemplar revocation.
  13. `[GET /api/v1/governance/assets]` verifies asset list.
  14. `[GET /api/v1/evaluation/suite]` verifies 30-payload benchmark suite.
  15. `[GET /api/v1/evaluation/report]` verifies 0% prompt-injection bypass rate.
* **Result:** **100% PASS (All 16 test suites green)**

---

## 9. Operational Runbook & Developer Quickstart

### 9.1 Prerequisites
* Python 3.11+ (Python 3.14/3.13 supported)
* PostgreSQL 16+ running locally on port 5432 (or configured in `.env`)
* Node.js 20+ (for frontend client)

### 9.2 Initial Environment Setup
```powershell
# 1. Navigate to backend directory
cd c:\projects\SentraX\backend

# 2. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 3. Verify dependencies
pip install -r requirements.txt
```

### 9.3 Database Initialization & Migration
```powershell
# 1. Execute Alembic migration to latest revision
alembic upgrade head

# 2. Populate realistic SOC telemetry and benchmark records
python -m app.seed_data

# 3. Verify database integrity and immutability trigger
python tests/test_db_schema.py
```

### 9.4 Launching the Backend Server
```powershell
# Start Uvicorn development server on port 8000
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
* **Interactive Swagger UI:** Open `http://localhost:8000/docs` in your browser.
* **Alternative ReDoc UI:** Open `http://localhost:8000/redoc`.

### 9.5 Connecting the React Frontend
In [`c:\projects\SentraX\frontend\.env`](file:///c:/projects/SentraX/frontend/.env):
```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```
Start the frontend development server:
```powershell
cd c:\projects\SentraX\frontend
npm run dev
```
Open `http://localhost:5173/` and sign in with any seeded operator account:
* **Analyst:** `analyst_01` / `sentrax2026`
* **Team Lead:** `teamlead_mercer` / `sentrax2026`
* **Admin:** `admin_sys` / `sentrax2026`

