# Sentra-X: Production PostgreSQL 16 Database Architecture & Entity-Relationship Model

> **Document Type:** Production Database Architecture & Technical Reference Manual  
> **System Name:** Sentra-X — Evidence-Grounded and Uncertainty-Aware Human-in-the-Loop SOC Alert Triage Copilot  
> **Lead Architect / Author:** Asad Ullah Zafar (`CS-24082`), Frontend, Database & Full-Stack Integration Lead  
> **Academic Institution:** Department of Computer and Information Systems Engineering, NED University of Engineering & Technology  
> **Academic Term:** Fall Semester 2026 (`Teaching: Aug 17 – Nov 27, 2026` | Official Deliverable Companion)  
> **Authoritative Specification Baseline:** Sentra-X Software Requirements Specification (**SRS v1.4**, October 14, 2026 — Section 7.1, Section 7.2.1, Section 7.3)  
> **Companion References:** [`sentraX_design_document.md`](file:///c:/projects/SentraX/docs/sentraX_design_document.md) (SDD v1.0), [`sentraX_srs.md`](file:///c:/projects/SentraX/docs/sentraX_srs.md) (SRS v1.4), [`sentraX_project_plan.md`](file:///c:/projects/SentraX/docs/sentraX_project_plan.md) (SPMP v1.1), [`backend_architecture_and_api_documentation.md`](file:///c:/projects/SentraX/docs/backend_architecture_and_api_documentation.md), [`database_entity_relationship_diagram.pdf`](file:///c:/projects/SentraX/docs/database_entity_relationship_diagram.pdf), [`gemini-docs/decisions.md`](file:///c:/projects/SentraX/gemini-docs/decisions.md), [`gemini-docs/flow.md`](file:///c:/projects/SentraX/gemini-docs/flow.md)

---

## Table of Contents

1. [Executive Summary & Database Architecture](#1-executive-summary--database-architecture)
2. [Visual Entity-Relationship Model (Mermaid ERD)](#2-visual-entity-relationship-model-mermaid-erd)
3. [Column-Level Data Dictionary (SRS v1.4 §7.2.1 Compliant)](#3-column-level-data-dictionary-srs-v14-721-compliant)
   * [3.1 Table: `users` (Identity & RBAC)](#31-table-users-identity--rbac)
   * [3.2 Table: `assets` (Host & Asset Criticality Registry)](#32-table-assets-host--asset-criticality-registry)
   * [3.3 Table: `alerts` (Ingested Wazuh SIEM Events)](#33-table-alerts-ingested-wazuh-siem-events)
   * [3.4 Table: `evidence_packs` (Sanitized Telemetry & Citations)](#34-table-evidence_packs-sanitized-telemetry--citations)
   * [3.5 Table: `ai_assessments` (LLM Triage & Guardrail Dispositions)](#35-table-ai_assessments-llm-triage--guardrail-dispositions)
   * [3.6 Table: `analyst_decisions_audit` (Immutable Tamper-Evident Log)](#36-table-analyst_decisions_audit-immutable-tamper-evident-log)
   * [3.7 Table: `feedback_exemplars` (Dynamic Few-Shot Calibration)](#37-table-feedback_exemplars-dynamic-few-shot-calibration)
4. [High-Speed Indexing Architecture & Latency Guarantees](#4-high-speed-indexing-architecture--latency-guarantees)
5. [Foreign Key Constraints, Cascade Rules & Integrity Policies](#5-foreign-key-constraints-cascade-rules--integrity-policies)
6. [PostgreSQL Immutability Trigger Implementation (`trg_audit_immutability`)](#6-postgresql-immutability-trigger-implementation-trg_audit_immutability)
7. [Dual-Upsert Pattern & Idempotent Retry AI Lifecycle (ADR 8.5)](#7-dual-upsert-pattern--idempotent-retry-ai-lifecycle-adr-85)
8. [Database Driver Topology (Psycopg v3 Sync & Async)](#8-database-driver-topology-psycopg-v3-sync--async)

---

## 1. Executive Summary & Database Architecture

The Sentra-X database is hosted on **PostgreSQL 16** and serves as the authoritative, durable persistence boundary for Security Operations Center (SOC) alert triage, AI threat evaluations, and compliance audits.

To satisfy the functional requirements (`FR-1` through `FR-10`) and rigorous non-functional targets (`NFR-1` latency $\le 8.0\text{s}$, `NFR-3` prompt injection containment, `NFR-4` 12-month immutability & sub-50ms lookup), the database architecture adheres to four core engineering principles:

1. **Local Data Boundary (§8.3, DR-10):** All raw Wazuh JSON payloads, Sysmon process executions, endpoint IPs, and analyst audit records remain strictly within the local PostgreSQL container. Only sanitized, prompt-isolated payloads are dispatched to external LLM APIs (Google Gemini / Anthropic Claude).
2. **Relational Strictness & Domain Constraints (§5.7, DR-1, DR-3):** Severity scales, lifecycle states, user roles, and asset tiers are validated through database-level `CHECK` constraints, preventing corrupt or out-of-spec data from entering the storage layer.
3. **Database Trigger-Enforced Immutability (§7.3, FR-6, NFR-4):** Historical decision records in `analyst_decisions_audit` are governed by a PostgreSQL PL/pgSQL `BEFORE UPDATE OR DELETE` trigger (`trg_audit_immutability`) that raises an unrecoverable exception, making the audit log tamper-evident in alignment with SOC 2 (CC6.8) and ISO 27001 (A.12.4.1) audit trail design principles. In production environments, `TRUNCATE` privileges are revoked from the application role.
4. **Sub-50ms Partial Indexing (§7.3, NFR-4):** In-context few-shot calibration queries operate against a filtered composite index (`WHERE is_active = TRUE`), meeting the NFR-4 target of $< 50\text{ms}$ exemplar lookup without scanning revoked historical records.

---

## 2. Visual Entity-Relationship Model (Mermaid ERD)

The Entity-Relationship model below details all seven core tables, their cardinality relationships, primary/foreign keys, and SRS v1.4 data types.

```mermaid
%%{init: {'er': {'layoutDirection': 'LR', 'entityPadding': 10, 'fontSize': 11}}}%%
erDiagram
    USERS ||--o{ ANALYST_DECISIONS_AUDIT : "records (user_id)"
    USERS ||--o{ FEEDBACK_EXEMPLARS : "authors (created_by)"
    USERS ||--o{ FEEDBACK_EXEMPLARS : "revokes (revoked_by)"
    USERS ||--o{ ASSETS : "updates (updated_by)"
    ASSETS ||--o{ ALERTS : "generates (agent_id)"
    ALERTS ||--o| EVIDENCE_PACKS : "assembled_into (alert_id)"
    ALERTS ||--o| AI_ASSESSMENTS : "evaluated_by (alert_id)"
    ALERTS ||--o{ ANALYST_DECISIONS_AUDIT : "dispositioned_by (alert_id)"
    ALERTS ||--o{ FEEDBACK_EXEMPLARS : "calibrates_from (source_alert_id)"

    USERS {
        uuid id PK "gen_random_uuid()"
        varchar_64 username UK "Case-sensitive handle"
        varchar_255 email UK "Corporate email"
        varchar_255 password_hash "Salted bcrypt (cost >= 10)"
        varchar_16 role "CHECK: Analyst | TeamLead | Admin"
        boolean is_active "Default TRUE"
        timestamptz created_at "Default NOW()"
    }

    ASSETS {
        varchar_64 agent_id PK "Wazuh Agent ID string (0-translation)"
        varchar_255 hostname "Machine hostname / FQDN"
        varchar_45 ip_address "Host IP (nullable for agents without IP)"
        varchar_16 criticality_tier "CHECK: LOW | MEDIUM | HIGH | CRITICAL"
        text description "Host business role"
        uuid updated_by FK "Modifying user (users.id)"
        timestamptz created_at "Default NOW()"
        timestamptz updated_at "Default NOW()"
    }

    ALERTS {
        uuid id PK "gen_random_uuid()"
        varchar_128 wazuh_alert_id UK "Upstream event deduplication key"
        varchar_32 rule_id "Wazuh detection signature ID"
        integer rule_level "CHECK: 0 to 15 (L_min >= 4)"
        text rule_description "Detection alert title"
        varchar_255 agent_name "Target host name snapshot"
        varchar_64 agent_id FK "FK assets(agent_id)"
        varchar_45 src_ip "Source / Attacker IP"
        text process_signature "Normalized process/command string"
        jsonb raw_payload "Original unaltered Wazuh JSON"
        jsonb mitre_tactics "Parsed ATT&CK tactics array"
        jsonb mitre_techniques "Parsed ATT&CK technique IDs"
        varchar_32 status "CHECK: 5-state lifecycle enum"
        smallint retry_count "Default 0 (reset by Retry AI)"
        timestamptz alert_timestamp "Original Wazuh event timestamp"
        timestamptz ingested_at "Default NOW()"
        timestamptz updated_at "Default NOW()"
    }

    EVIDENCE_PACKS {
        uuid id PK "gen_random_uuid()"
        uuid alert_id FK "UNIQUE 1-to-1 FK alerts(id)"
        jsonb pack_json "Sanitized Evidence Pack tree"
        jsonb valid_dot_keys "Precomputed dot-notation paths"
        boolean injection_suspect "Default FALSE"
        jsonb injected_exemplar_ids "Array of injected exemplar IDs"
        timestamptz created_at "Default NOW()"
        timestamptz updated_at "Default NOW() (ADR 8.5)"
    }

    AI_ASSESSMENTS {
        uuid id PK "gen_random_uuid()"
        uuid alert_id FK "UNIQUE 1-to-1 FK alerts(id)"
        varchar_32 raw_verdict "CHECK: TRUE_POS | FALSE_POS | NEEDS_REV"
        varchar_16 raw_severity "CHECK: LOW | MEDIUM | HIGH | CRITICAL"
        varchar_32 effective_verdict "Post-FR3 guardrail verdict"
        varchar_16 effective_severity "Post-FR3 safety floor severity"
        float confidence_score "CHECK: 0.00 to 1.00 (< 0.60 abstains)"
        jsonb cited_evidence_keys "Dot-notation telemetry citations"
        text explanation "Plain language justification (<= 500 chars)"
        boolean safety_floor_triggered "Default FALSE"
        boolean abstention_triggered "Default FALSE"
        text guardrail_audit_note "Deterministic rule explanation"
        varchar_32 llm_provider "Active adapter: gemini | claude | mock"
        varchar_64 model_name "Model ID (e.g. gemini-3.1-flash-lite)"
        integer inference_latency_ms "API latency (alias: latency_ms)"
        smallint retry_count "Default 0 (0 to 3 attempts)"
        timestamptz created_at "Default NOW()"
        timestamptz updated_at "Default NOW() (ADR 8.5)"
    }

    ANALYST_DECISIONS_AUDIT {
        uuid id PK "gen_random_uuid()"
        uuid alert_id FK "FK alerts(id) ON DELETE RESTRICT"
        uuid user_id FK "FK users(id) ON DELETE RESTRICT"
        varchar_32 action_taken "CHECK: APPROVE | OVERRIDE | ESCALATE | RETRY_AI | MANUAL_TRIAGE_CLOSURE | RESOLVE_ESCALATION"
        varchar_32 previous_verdict "Pre-decision verdict"
        varchar_16 previous_severity "Pre-decision severity"
        varchar_32 final_verdict "Post-decision authoritative verdict"
        varchar_16 final_severity "Post-decision authoritative severity"
        text rationale "Mandatory >= 10 chars on OVERRIDE/CLOSE"
        boolean exemplar_created "Default FALSE"
        timestamptz created_at "Default NOW() (APPEND-ONLY)"
    }

    FEEDBACK_EXEMPLARS {
        integer id PK "SERIAL AUTOINCREMENT"
        uuid source_alert_id FK "FK alerts(id) ON DELETE SET NULL"
        varchar_32 rule_id "Targeted Wazuh rule ID"
        text process_signature "Tier 1 matching key (nullable for non-process alerts)"
        varchar_16 asset_criticality "Tier 2 matching key"
        varchar_32 calibrated_verdict "CHECK: TRUE_POSITIVE | FALSE_POSITIVE"
        varchar_16 calibrated_severity "CHECK: LOW | MEDIUM | HIGH | CRITICAL"
        text rationale "Analyst justification (>= 10 chars)"
        boolean is_active "Default TRUE (Revocation flag)"
        integer match_hit_count "Default 0 (Usage counter)"
        uuid created_by FK "FK users(id) Author of override"
        uuid revoked_by FK "FK users(id) Team Lead who revoked"
        timestamptz revoked_at "Timestamp of revocation"
        timestamptz created_at "Default NOW()"
    }

    SYSTEM_CONFIGURATIONS {
        integer id PK "Singleton ID (1)"
        varchar_255 wazuh_endpoint "Wazuh API endpoint"
        varchar_32 wazuh_status "CONNECTED | DEGRADED | OFFLINE"
        integer polling_interval_seconds "Polling cadence (default 30)"
        integer min_rule_level "Minimum rule level (default 4)"
        varchar_32 llm_provider "Gemini | Claude | Mock"
        varchar_64 model_name "Target model identifier"
        float abstention_threshold "Uncertainty boundary (default 0.60)"
        integer max_exemplars_injected "Max few-shot exemplars (default 2)"
        timestamptz last_sync_timestamp "Last telemetry heartbeat"
        timestamptz updated_at "Default NOW()"
    }
```

---

## 3. Column-Level Data Dictionary (SRS v1.4 §7.2.1 Compliant)

All timestamps are stored in **UTC (`TIMESTAMPTZ`)**. Nullability and database constraints strictly enforce system invariants.

### 3.1 Table: `users` (Identity & RBAC)
Stores user identities, salted password credentials, and role assignments (`FR-8`).

| Column Name | SQL Type | Nullable | Default / Constraints | Operational Purpose |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `UUID` | No | `PRIMARY KEY`, `DEFAULT gen_random_uuid()` | Internal unique identifier for user account. |
| `username` | `VARCHAR(64)` | No | `UNIQUE (uq_users_username)` | Case-sensitive account handle used for login. |
| `email` | `VARCHAR(255)` | No | `UNIQUE (uq_users_email)` | Corporate email address. |
| `password_hash` | `VARCHAR(255)` | No | Salted `bcrypt` hash (`cost ≥ 10`) | Plaintext passwords are never stored or transmitted in responses. |
| `role` | `VARCHAR(16)` | No | `CHECK (role IN ('Analyst', 'TeamLead', 'Admin'))` | RBAC access tier governing API permissions and UI views. |
| `is_active` | `BOOLEAN` | No | `DEFAULT TRUE` | Soft-disable switch; deactivated accounts are immediately rejected with HTTP 403. |
| `created_at` | `TIMESTAMPTZ` | No | `DEFAULT NOW()` | Account creation timestamp. |

---

### 3.2 Table: `assets` (Host & Asset Criticality Registry)
Maintains host criticality tiers for monitored Wazuh agents (`FR-9`).

| Column Name | SQL Type | Nullable | Default / Constraints | Operational Purpose |
| :--- | :--- | :---: | :--- | :--- |
| `agent_id` | `VARCHAR(64)` | No | `PRIMARY KEY` | Authentic Wazuh Agent ID string (e.g. `'001'`), enabling 0-translation joins with SIEM events. |
| `hostname` | `VARCHAR(255)` | No | None | Fully qualified domain name or machine hostname. |
| `ip_address` | `VARCHAR(45)` | No | IPv4 or IPv6 representation | Primary interface IP address. |
| `criticality_tier`| `VARCHAR(16)` | No | `DEFAULT 'MEDIUM'`, `CHECK (criticality_tier IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'))` | Business asset tier injected into Evidence Pack (`FR-2`) and Tier 2 fallback matching (`FR-4`). |
| `description` | `TEXT` | Yes | None | Operational context (e.g., "Primary Active Directory DC"). |
| `updated_by` | `UUID` | Yes | `FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL` | ID of the Team Lead or Admin who updated the tier (`FR-9`, AC-17). `NULL` when auto-registered. |
| `created_at` | `TIMESTAMPTZ` | No | `DEFAULT NOW()` | Host registration timestamp. |
| `updated_at` | `TIMESTAMPTZ` | No | `DEFAULT NOW()` | Last criticality tier modification timestamp. |

---

### 3.3 Table: `alerts` (Ingested Wazuh SIEM Events)
Stores raw and normalized alerts ingested from Wazuh (`FR-1`, `FR-5`).

| Column Name | SQL Type | Nullable | Default / Constraints | Operational Purpose |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `UUID` | No | `PRIMARY KEY`, `DEFAULT gen_random_uuid()` | Internal immutable UUID identifier. |
| `wazuh_alert_id` | `VARCHAR(128)` | No | `UNIQUE (uq_alerts_wazuh_alert_id)` | Unique upstream event ID from Wazuh Manager, enforcing idempotent deduplication (`AC-1`). |
| `rule_id` | `VARCHAR(32)` | No | None | Wazuh detection signature ID (e.g., `'100201'`). |
| `rule_level` | `INTEGER` | No | `CHECK (rule_level BETWEEN 0 AND 15)` | Wazuh alert severity score ($0$ to $15$). Events with `level < 4` dropped by `FR-1`. |
| `rule_description`| `TEXT` | No | None | Human-readable threat detection summary. |
| `agent_name` | `VARCHAR(255)` | No | None | Machine hostname snapshot recorded at time of alert ingestion. |
| `agent_id` | `VARCHAR(64)` | No | `FOREIGN KEY (agent_id) REFERENCES assets(agent_id) ON DELETE RESTRICT` | Target host agent where detection occurred. |
| `src_ip` | `VARCHAR(45)` | Yes | None | Source / Attacker IP address extracted from telemetry. |
| `process_signature`| `TEXT` | Yes | None | Normalized process/script execution string for Tier 1 few-shot matching. |
| `raw_payload` | `JSONB` | No | None | Complete unaltered upstream Wazuh JSON telemetry payload. |
| `mitre_tactics` | `JSONB` | No | `DEFAULT '[]'::jsonb` | Parsed array of MITRE ATT&CK tactics (e.g., `["Credential Access"]`). |
| `mitre_techniques`| `JSONB` | No | `DEFAULT '[]'::jsonb` | Parsed array of MITRE ATT&CK technique IDs (e.g., `["T1003.001"]`). |
| `status` | `VARCHAR(32)` | No | `DEFAULT 'PENDING_REVIEW'`, `CHECK (status IN ('PENDING_REVIEW', 'AWAITING_ANALYST', 'NEEDS_MANUAL_TRIAGE', 'ESCALATED', 'CLOSED'))` | Five-state closed-loop finite state machine status (§6.4). |
| `retry_count` | `SMALLINT` | No | `DEFAULT 0` | Triage retry counter; reset to 0 by `Retry AI Triage` (`FR-6`, `UC-7`). |
| `alert_timestamp`| `TIMESTAMPTZ` | No | None | Original event generation timestamp extracted from Wazuh alert JSON. |
| `ingested_at` | `TIMESTAMPTZ` | No | `DEFAULT NOW()` | Timestamp when Sentra-X received and stored the alert. |
| `updated_at` | `TIMESTAMPTZ` | No | `DEFAULT NOW()` | Last status transition timestamp. |

---

### 3.4 Table: `evidence_packs` (Sanitized Telemetry & Citations)
Structured, prompt-injection sanitized telemetry bundles compiled for LLM inference (`FR-2`).

| Column Name | SQL Type | Nullable | Default / Constraints | Operational Purpose |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `UUID` | No | `PRIMARY KEY`, `DEFAULT gen_random_uuid()` | Unique Evidence Pack identifier. |
| `alert_id` | `UUID` | No | `UNIQUE (uq_evidence_packs_alert_id)`, `FOREIGN KEY (alert_id) REFERENCES alerts(id) ON DELETE CASCADE` | 1-to-1 relationship with source alert. |
| `pack_json` | `JSONB` | No | None | Complete sanitized structured tree (`alert_metadata`, `asset_context`, `telemetry_payload`, `temporal_context`). |
| `valid_dot_keys` | `JSONB` | No | `DEFAULT '[]'::jsonb` | Precomputed allowed dot-notation paths (e.g., `["telemetry_payload.data.win.eventdata.CommandLine"]`). |
| `injection_suspect`| `BOOLEAN` | No | `DEFAULT FALSE` | True if `PromptSanitizer` flagged delimiter-spoofing or instruction override patterns. |
| `injected_exemplar_ids`| `JSONB`| No | `DEFAULT '[]'::jsonb` | Array of feedback exemplar IDs dynamically injected into prompt context. |
| `created_at` | `TIMESTAMPTZ` | No | `DEFAULT NOW()` | Initial pack assembly timestamp. |
| `updated_at` | `TIMESTAMPTZ` | No | `DEFAULT NOW()` | Pack refresh timestamp (updated on `Retry AI` upsert per ADR 8.5). |

---

### 3.5 Table: `ai_assessments` (LLM Triage & Guardrail Dispositions)
Stores LLM inference evaluations alongside post-guardrail effective dispositions (`FR-2`, `FR-3`).

| Column Name | SQL Type | Nullable | Default / Constraints | Operational Purpose |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `UUID` | No | `PRIMARY KEY`, `DEFAULT gen_random_uuid()` | Unique Assessment identifier. |
| `alert_id` | `UUID` | No | `UNIQUE (uq_ai_assessments_alert_id)`, `FOREIGN KEY (alert_id) REFERENCES alerts(id) ON DELETE CASCADE` | 1-to-1 relationship with source alert. |
| `raw_verdict` | `VARCHAR(32)` | No | `CHECK (raw_verdict IN ('TRUE_POSITIVE', 'FALSE_POSITIVE', 'NEEDS_ANALYST_REVIEW'))` | Raw unverified verdict returned by hosted LLM. |
| `raw_severity` | `VARCHAR(16)` | No | `CHECK (raw_severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'))` | Raw severity proposed by hosted LLM. |
| `effective_verdict`| `VARCHAR(32)`| No | `CHECK (effective_verdict IN ('TRUE_POSITIVE', 'FALSE_POSITIVE', 'NEEDS_ANALYST_REVIEW'))` | Deterministic verdict enforced after `RulesEngine` safety floor and abstention rules (`FR-3`). |
| `effective_severity`| `VARCHAR(16)`| No | `CHECK (effective_severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'))` | Deterministic severity enforced after Safety Floor rules (`FR-3`). |
| `confidence_score`| `FLOAT` | No | `CHECK (confidence_score BETWEEN 0.0 AND 1.0)` | Model confidence score ($0.00$ to $1.00$). Score $< 0.60$ forces abstention. |
| `cited_evidence_keys`| `JSONB` | No | `DEFAULT '[]'::jsonb` | Dot-notation citation paths validated against `valid_dot_keys`. |
| `explanation` | `TEXT` | No | Character limit $\le 500$ chars | Plain language justification explaining the verdict. |
| `safety_floor_triggered`| `BOOLEAN`| No | `DEFAULT FALSE` | True if raw downgrade was blocked on high/critical alert (`rule_level ≥ 10`). |
| `abstention_triggered`| `BOOLEAN`| No | `DEFAULT FALSE` | True if confidence $< 0.60$, citations were empty/invalid, or contradiction occurred. |
| `guardrail_audit_note`| `TEXT` | Yes | None | Explanatory note detailing which deterministic rule intervened. |
| `llm_provider` | `VARCHAR(32)` | Yes | None | Active adapter provider (`gemini`, `claude`, or `mock`). |
| `model_name` | `VARCHAR(64)` | No | None | Specific LLM model identifier (e.g. `gemini-3.1-flash-lite`). |
| `inference_latency_ms`| `INTEGER` | No | Alias: `latency_ms` | Outbound LLM API round-trip inference latency in milliseconds. |
| `retry_count` | `SMALLINT` | No | `DEFAULT 0`, `CHECK (retry_count BETWEEN 0 AND 3)` | Automated API retry attempts (times out after 3 retries $\to$ `NEEDS_MANUAL_TRIAGE`). |
| `created_at` | `TIMESTAMPTZ` | No | `DEFAULT NOW()` | Initial assessment creation timestamp. |
| `updated_at` | `TIMESTAMPTZ` | No | `DEFAULT NOW()` | Assessment update timestamp (refreshed on `Retry AI` upsert per ADR 8.5). |

---

### 3.6 Table: `analyst_decisions_audit` (Immutable Tamper-Evident Log)
Append-only legal audit log of all human dispositions (`FR-6`, `NFR-4`, SOC 2 / ISO 27001).

| Column Name | SQL Type | Nullable | Default / Constraints | Operational Purpose |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `UUID` | No | `PRIMARY KEY`, `DEFAULT gen_random_uuid()` | Immutable Audit Record identifier. |
| `alert_id` | `UUID` | No | `FOREIGN KEY (alert_id) REFERENCES alerts(id) ON DELETE RESTRICT` | Referenced alert. Parent cannot be deleted while audit row exists. |
| `user_id` | `UUID` | No | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT` | Authenticated user who performed the action (`FR-8`). |
| `action_taken` | `VARCHAR(32)` | No | `CHECK (action_taken IN ('APPROVE', 'OVERRIDE', 'ESCALATE', 'RETRY_AI', 'MANUAL_TRIAGE_CLOSURE', 'RESOLVE_ESCALATION'))` | Action verb recorded during triage. |
| `previous_verdict`| `VARCHAR(32)`| Yes | None | Effective verdict before the human action was taken. |
| `previous_severity`| `VARCHAR(16)`| Yes | None | Effective severity before the human action was taken. |
| `final_verdict` | `VARCHAR(32)` | Yes | `NULL` for `ESCALATE` and `RETRY_AI` | Authoritative verdict recorded in audit trail. |
| `final_severity` | `VARCHAR(16)` | Yes | `NULL` for `ESCALATE` and `RETRY_AI` | Authoritative severity recorded in audit trail. |
| `rationale` | `TEXT` | Yes | Mandatory $\ge 10$ characters on `OVERRIDE`, `MANUAL_TRIAGE_CLOSURE`, `RESOLVE_ESCALATION` | Analyst justification for auditability and feedback calibration. |
| `exemplar_created`| `BOOLEAN` | No | `DEFAULT FALSE` | True if this action generated a new few-shot calibration exemplar (`FR-4`). |
| `created_at` | `TIMESTAMPTZ` | No | `DEFAULT NOW()` | Immutable timestamp of record insertion. |

> [!CAUTION]
> **Strict Immutability Guarantee:** This table intentionally lacks an `updated_at` column. The PostgreSQL trigger `trg_audit_immutability` executes `BEFORE UPDATE OR DELETE` and raises an unrecoverable exception, permanently prohibiting any modification or removal of historical decision rows.

---

### 3.7 Table: `feedback_exemplars` (Dynamic Few-Shot Calibration)
Few-shot calibration store enabling in-context learning without model retraining (`FR-4`).

| Column Name | SQL Type | Nullable | Default / Constraints | Operational Purpose |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `SERIAL` (`INT`) | No | `PRIMARY KEY`, `AUTOINCREMENT` | Integer autoincrement PK (Decision 8.4) for high-speed retrieval. |
| `source_alert_id`| `UUID` | Yes | `FOREIGN KEY (source_alert_id) REFERENCES alerts(id) ON DELETE SET NULL` | Provenance link to alert where override occurred. |
| `rule_id` | `VARCHAR(32)` | No | None | Wazuh detection signature ID targeted by calibration. |
| `process_signature`| `TEXT` | No | None | Normalized process/script string for Tier 1 signature matching. |
| `asset_criticality`| `VARCHAR(16)`| No | `CHECK (asset_criticality IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'))` | Host tier for Tier 2 fallback matching. |
| `calibrated_verdict`| `VARCHAR(32)`| No | `CHECK (calibrated_verdict IN ('TRUE_POSITIVE', 'FALSE_POSITIVE'))` | Human-corrected authoritative ground truth. |
| `calibrated_severity`| `VARCHAR(16)`| No | `CHECK (calibrated_severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'))` | Human-corrected authoritative severity. |
| `rationale` | `TEXT` | No | Character length $\ge 10$ chars | Analyst justification injected into prompt context. |
| `is_active` | `BOOLEAN` | No | `DEFAULT TRUE` | Team Lead revocation switch. Inactive exemplars excluded from future prompt retrieval (`AC-9`). |
| `match_hit_count` | `INTEGER` | No | `DEFAULT 0` | Hit counter incremented whenever exemplar is selected in context. |
| `created_by` | `UUID` | Yes | `FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL` | Analyst who authored the override (`user_id` in SRS v1.4). |
| `revoked_by` | `UUID` | Yes | `FOREIGN KEY (revoked_by) REFERENCES users(id) ON DELETE SET NULL` | Team Lead who revoked this exemplar (`FR-4`, §6.5 Sequence 2). |
| `revoked_at` | `TIMESTAMPTZ` | Yes | None | Timestamp when revocation was executed. |
| `created_at` | `TIMESTAMPTZ` | No | `DEFAULT NOW()` | Creation timestamp. |

---

## 4. High-Speed Indexing Architecture & Latency Guarantees

To satisfy the non-functional latency targets (`NFR-4: < 50ms lookup` and `NFR-5: >= 5 alerts/sec throughput`), the following specialized B-Tree indexes are deployed in PostgreSQL:

| Index Name | Target Table | Indexed Columns / Definition | Target Requirement & Latency Impact |
| :--- | :--- | :--- | :--- |
| `uq_alerts_wazuh_alert_id` | `alerts` | `UNIQUE (wazuh_alert_id)` | $O(1)$ deduplication during Wazuh polling (`FR-1`). Ensures idempotent alert ingestion. |
| `ix_alerts_queue_priority` | `alerts` | `(status, ingested_at ASC)` | High-speed Analyst Queue sorting (`FR-5`). Delivers paginated slices meeting the `< 50ms` UI responsiveness target. |
| `ix_alerts_agent_timestamp` | `alerts` | `(agent_id, alert_timestamp DESC)` | 24-hour lookback correlation by agent (`FR-2`). Enables efficient index scans within correlation windows. |
| `ix_alerts_src_ip_timestamp` | `alerts` | `(src_ip, alert_timestamp DESC) WHERE src_ip IS NOT NULL` | 24-hour lookback correlation by source IP (`FR-2`). Supports BitmapOr planning with agent index. |
| `ix_exemplars_retrieval` | `feedback_exemplars` | `(rule_id, asset_criticality, created_at DESC) WHERE is_active = TRUE` | **Partial Composite Index (`NFR-4`):** Retrieves the top 2 active few-shot exemplars, meeting `< 50ms` SLA. |
| `ix_ai_assessments_alert_id`| `ai_assessments`| `(alert_id)` | Foreign key reverse lookup for alert detail modal assembly (`FR-5`). |
| `ix_evidence_packs_alert_id`| `evidence_packs`| `(alert_id)` | Foreign key reverse lookup for evidence tree retrieval. |
| `ix_audit_alert_id` | `analyst_decisions_audit`| `(alert_id)` | Fast lookup for historical audit timeline in modal footer. |
| `ix_audit_user_id` | `analyst_decisions_audit`| `(user_id)` | Aggregates per-analyst performance and agreement rates (`FR-7`). |

---

## 5. Foreign Key Constraints, Cascade Rules & Integrity Policies

```
[ASSETS] ──(agent_id: ON DELETE RESTRICT)──► [ALERTS]
                                                ├──(alert_id: ON DELETE CASCADE)──► [EVIDENCE_PACKS]
                                                ├──(alert_id: ON DELETE CASCADE)──► [AI_ASSESSMENTS]
                                                ├──(alert_id: ON DELETE RESTRICT)─► [ANALYST_DECISIONS_AUDIT]
                                                └──(source_alert_id: SET NULL)──► [FEEDBACK_EXEMPLARS]
[USERS] ──(user_id: ON DELETE RESTRICT)──► [ANALYST_DECISIONS_AUDIT]
[USERS] ──(created_by: ON DELETE SET NULL)─► [FEEDBACK_EXEMPLARS]
[USERS] ──(revoked_by: ON DELETE SET NULL)─► [FEEDBACK_EXEMPLARS]
[USERS] ──(updated_by: ON DELETE SET NULL)─► [ASSETS]
```

1. **Audit Protection (`RESTRICT`):** `ALERTS` and `USERS` cannot be deleted if referenced by an `ANALYST_DECISIONS_AUDIT` entry (`ON DELETE RESTRICT`), preventing accidental deletion of legally binding SOC actions.
2. **Triage Cascades (`CASCADE`):** Deleting a transient alert cleans up its associated `EVIDENCE_PACKS` and `AI_ASSESSMENTS` (`ON DELETE CASCADE`), preventing orphaned JSON telemetry bloat.
3. **Exemplar & Asset Preservation (`SET NULL`):** Deleting a user sets `created_by`, `revoked_by`, or `updated_by` to `NULL` (`ON DELETE SET NULL`), ensuring calibration exemplars and asset registries remain functional.

---

## 6. PostgreSQL Immutability Trigger Implementation (`trg_audit_immutability`)

### PL/pgSQL Function & Trigger Definition
```sql
-- Trigger Function enforcing Append-Only Immutability
CREATE OR REPLACE FUNCTION prevent_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'analyst_decisions_audit is append-only. UPDATE and DELETE operations are permanently prohibited on this table (FR-6, NFR-4, SOC 2 / ISO 27001 compliance).';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Trigger binding to analyst_decisions_audit
CREATE TRIGGER trg_audit_immutability
BEFORE UPDATE OR DELETE ON analyst_decisions_audit
FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();
```

### Verification Proof
When any client or backend thread issues an `UPDATE` or `DELETE` against `analyst_decisions_audit`, PostgreSQL terminates the transaction with code `P0001` (RaiseException):

```text
ERROR:  analyst_decisions_audit is append-only. UPDATE and DELETE operations are permanently prohibited on this table (FR-6, NFR-4).
CONTEXT:  PL/pgSQL function prevent_audit_modification() line 3 at RAISE
```

> [!NOTE] Row-Level Trigger Scope & TRUNCATE Protection
> PostgreSQL `FOR EACH ROW` triggers do not fire on `TRUNCATE` operations. In production deployments, immutability against table truncation is enforced at the database role level by revoking `TRUNCATE` permissions on `analyst_decisions_audit` from the application database user (`REVOKE TRUNCATE ON analyst_decisions_audit FROM sentrax;`).


---

## 7. Dual-Upsert Pattern & Idempotent Retry AI Lifecycle (ADR 8.5)

When an analyst triggers **`Retry AI Triage`** (`FR-6`, `UC-7`):
1. `alerts.status` transitions from `NEEDS_MANUAL_TRIAGE` to `PENDING_REVIEW`, and `alerts.retry_count` is reset to 0.
2. An audit row is inserted into `analyst_decisions_audit` with `action_taken = 'RETRY_AI'`.
3. When the AI triage pipeline re-processes the alert, it executes an **UPSERT** on both `evidence_packs` and `ai_assessments`:
   ```sql
   INSERT INTO ai_assessments (id, alert_id, raw_verdict, raw_severity, effective_verdict, effective_severity, confidence_score, cited_evidence_keys, explanation, safety_floor_triggered, abstention_triggered, guardrail_audit_note, llm_provider, model_name, inference_latency_ms, retry_count, created_at, updated_at)
   VALUES (...)
   ON CONFLICT (alert_id) DO UPDATE SET
       raw_verdict = EXCLUDED.raw_verdict,
       raw_severity = EXCLUDED.raw_severity,
       effective_verdict = EXCLUDED.effective_verdict,
       effective_severity = EXCLUDED.effective_severity,
       confidence_score = EXCLUDED.confidence_score,
       cited_evidence_keys = EXCLUDED.cited_evidence_keys,
       explanation = EXCLUDED.explanation,
       safety_floor_triggered = EXCLUDED.safety_floor_triggered,
       abstention_triggered = EXCLUDED.abstention_triggered,
       guardrail_audit_note = EXCLUDED.guardrail_audit_note,
       llm_provider = EXCLUDED.llm_provider,
       model_name = EXCLUDED.model_name,
       inference_latency_ms = EXCLUDED.inference_latency_ms,
       retry_count = EXCLUDED.retry_count,
       updated_at = NOW();
   ```
This preserves the original `created_at` timestamp while updating `updated_at`, allowing SOC engineers to calculate latency between initial triage and human-requested retry evaluations.

---

## 8. Database Driver Topology (Psycopg v3 Sync & Async)

Sentra-X standardizes on **`psycopg` (v3)** across the entire Python backend, eliminating legacy dual-driver conflicts (`asyncpg` vs `psycopg2-binary`):

* **Synchronous Pipeline & Worker:** `postgresql+psycopg://sentrax:sentrax@localhost:5432/sentrax` (used by Wazuh poller, migration scripts, and seeders via SQLAlchemy 2.0 `Session`).
* **Asynchronous Web Routes:** `postgresql+psycopg_async://sentrax:sentrax@localhost:5432/sentrax` (used by FastAPI asynchronous endpoints via SQLAlchemy 2.0 `AsyncSession`).

---

## 9. Migration History & SRS v1.4 Integrity Hardening

### 9.1 Applied Alembic Migrations
1. **`0001_initial_schema`**: Core 7 tables, primary keys, and initial indexes.
2. **`0002_add_feedback_exemplars` / `0002_add_audit_trail_immutability`**: Added `feedback_exemplars` table and PostgreSQL trigger `trg_audit_immutability` ensuring append-only immutability on `analyst_decisions_audit` (Decision 8.4, AC-11).
3. **`0003_add_srs_check_constraints`**: Full SRS Section 7.2.1 Data Dictionary validation:
   - `alerts.ck_alerts_rule_level`: `CHECK (rule_level BETWEEN 0 AND 15)`
   - `alerts.ck_alerts_retry_count`: `CHECK (retry_count >= 0)`
   - `ai_assessments.ck_ai_assessments_confidence_score`: `CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0)`
   - `ai_assessments.ck_ai_assessments_retry_count`: `CHECK (retry_count BETWEEN 0 AND 3)`
   - `assets.criticality_tier`: `DEFAULT 'MEDIUM'` server default
   - `feedback_exemplars.user_id`: UUID FK referencing `users(id)` (synchronized synonym for `created_by`)
   - `feedback_exemplars.ck_exemplars_rationale_length`: `CHECK (length(rationale) >= 10)`
4. **`0004_add_system_configurations`**: Added `system_configurations` table to persist runtime settings (Wazuh poller, thresholds, model selection) across multi-worker uvicorn instances and container replicas.
5. **`0005_abr_audit_hardening`**: Forensic alignment with SRS v1.4 and AI pipeline specifications:
   - Dropped legacy correlation index `ix_alerts_agent_src_ts`; created dedicated `ix_alerts_agent_timestamp` and `ix_alerts_src_ip_timestamp` (optimizes 24h `OR` correlation).
   - Hardened `ck_audit_action_taken` to drop `MANUAL_TRIAGE_CLOSE`, standardizing on `MANUAL_TRIAGE_CLOSURE` for 100% analytics metric capture.
   - Altered `feedback_exemplars.process_signature` to `NULLABLE` (allows Tier 2 matching for non-process alert overrides).
   - Altered `assets.ip_address` to `NULLABLE` (prevents auto-registration worker crashes on IP-less agents).

### 9.2 Schema-Preserving Maintenance & Testing Scripts
To support robust automated testing against the actual PostgreSQL instance without destructive drops:
* **`backend/scripts/reset_db.py`**: Truncates all tables in FK order (`TRUNCATE ... RESTART IDENTITY CASCADE`) and seeds baseline records matching `demo_seed.json` (3 users, 6 assets, 16 alerts, 12 evidence packs, 12 assessments, 3 audits, 4 exemplars, 1 system config).
* **`backend/scripts/wipe_db.py`**: Safely clears all mock/test data while preserving 100% of the DDL schema, tables, constraints, indexes, and triggers across all 8 tables.
* **`backend/tests/test_db_schema.py`**: Strict CI test validating all 8 tables, SRS columns, 9 indexes, and 13 SRS check constraints directly against `information_schema` and `pg_constraint`.


