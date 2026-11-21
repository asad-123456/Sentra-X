# Sentra-X backend architecture and REST API

See [backend setup](../backend/README.md) for commands, [database documentation](database_documentation.md) for schema details, and [Wazuh sources](wazuh_alert_source.md) for ingestion setup. A running backend exposes its route schemas at `/docs` and `/openapi.json`. Several routers use dictionary contracts, so check the route and client service for field details.

## Runtime flow

1. The signed webhook, optional indexer poller, and JSONL replay call the same ingestion service. It parses and deduplicates alerts, auto-registers unseen assets as `MEDIUM`, persists qualifying alerts, and publishes IDs after commit. Alerts with unusable rule levels enter manual triage.
2. The FastAPI lifespan starts the worker and optional poller. The in-process queue carries pending IDs. The worker scans PostgreSQL on startup and periodically to recover pending rows, including rows ingested by a separate replay process.
3. The worker captures the pending attempt number and loads host context, correlations, and active exemplars in a short transaction. It assembles and sanitizes evidence and calls the model outside that transaction. Guardrails check citations and confidence and enforce severity floors for high-level Wazuh alerts. The store locks the alert before saving and writes the result only while the same attempt remains pending.
4. Successful assessments reach `AWAITING_ANALYST`. Failed triage reaches `NEEDS_MANUAL_TRIAGE`. Human decisions update the alert and append an audit row. Eligible decisions can create exemplars. `RETRY_AI` commits the pending state before re-enqueueing.
5. Most routes and the worker use synchronous SQLAlchemy sessions with Psycopg 3. The webhook delegates synchronous ingestion to a thread pool. An async session factory also exists.

The API uses bearer JWTs and database-backed checks on routes using the shared authorization dependency. Use `DEMO_MODE` only in an isolated lab. The live UI reads process settings from `/runtime/settings`. Change the backend environment and restart the process to apply runtime configuration.

## Endpoints

The application prefix is `/api/v1`. The paths in the first table already include their complete prefix.

| Method and path | Behavior |
| --- | --- |
| `GET /` | Service identity and documentation path. |
| `GET /api/health` | Database reachability in the response body. Check the JSON `status` for `HEALTHY` or `DEGRADED`. |
| `POST /api/webhooks/wazuh` | HMAC-authenticated alert ingestion. Accepts one JSON object or a list and returns ingestion counters. |

| Method and path relative to `/api/v1` | Behavior |
| --- | --- |
| `POST /auth/login`, `GET /auth/me` | Authenticate with username or email and password, then use the returned token to resolve the current user. |
| `GET /alerts`, `GET /alerts/counts`, `GET /alerts/{alert_id}` | Queue, counts, and details. Detail resolves exemplar records by the IDs saved with the evidence pack and includes them even if they have since been revoked. |
| `POST /alerts/{alert_id}/decision` | Record an analyst action or retry. Escalation resolution is restricted to TeamLead and Admin. |
| `GET /analytics`, `GET /analytics/export-csv` | TeamLead/Admin summary and audit CSV. Summary accepts `range` or `date_range` from `1d` through `90d` and optional `rule_id`. Export accepts an optional inclusive UTC `start_date` and `end_date` pair of up to 90 days and optional `rule_id`. Omitting dates preserves full-history export. |
| `GET /governance/exemplars`, `PATCH /governance/exemplars/{exemplar_id}` | TeamLead/Admin list. TeamLead can change exemplar activation. |
| `GET /governance/assets`, `PATCH /governance/assets/{agent_id}`, `POST /governance/assets` | Analyst/TeamLead/Admin can list assets. TeamLead/Admin can change tier and description. Admin can register assets with an optional IP address. |
| `GET /evaluation/suite`, `GET /evaluation/report`, `POST /evaluation/run`, `GET /evaluation/export-md`, `GET /evaluation/export-csv` | Admin benchmark inputs, latest report, explicit run, and exports. |
| `GET /runtime/settings` | Authenticated Analyst, TeamLead, and Admin can read effective non-secret ingestion settings, active worker count, provider, model, and guardrails. Poll interval appears only in poll mode. Worker status describes local threads. |
| `GET /admin/users`, `POST /admin/users`, `PATCH /admin/users/{user_id}/role`, `PATCH /admin/users/{user_id}/status` | Admin account management. |
| `GET /admin/config` | Deprecated, read-only view of historical admin settings. PATCH returns HTTP 405. |

### Queue and decisions

The queue accepts `tab` (`awaiting`, `escalated`, `closed`), `subStatus`, `status`, `search`, `severity`, `guardrail`, `assetTier`, `rule_id`, `page`, and `page_size` (1–100). It sorts review tabs by severity and ingestion time, and the closed tab by recent update.

Queue items and alert detail include `available_actions` for the current role, state, and saved assessment. The decision endpoint checks those conditions again. Alert detail includes the saved evidence pack under `evidence_pack.pack_json` when one exists. Evidence citation paths refer to that saved JSON.

Decision writes require the bearer token of an active user. The API looks up the user's current role and uses their account ID in the audit and any new exemplar.

| Action | Allowed current states | Result and requirements |
| --- | --- | --- |
| `APPROVE` | `AWAITING_ANALYST` | Closes the alert using the saved effective verdict and severity. If the model abstained, the analyst must select a binary verdict. Supplied values that disagree with the assessment where it is authoritative return HTTP 409. |
| `OVERRIDE` | `AWAITING_ANALYST` | Closes with an explicit verdict, severity, and rationale. Records a feedback exemplar. |
| `MANUAL_TRIAGE_CLOSURE` | `PENDING_REVIEW`, `NEEDS_MANUAL_TRIAGE` | Closes with an explicit verdict, severity, and rationale. The legacy spelling `MANUAL_TRIAGE_CLOSE` is accepted. |
| `ESCALATE` | `PENDING_REVIEW`, `AWAITING_ANALYST`, `NEEDS_MANUAL_TRIAGE` | Moves the alert to `ESCALATED`. The audit records a null final disposition. |
| `RESOLVE_ESCALATION` | `ESCALATED` | TeamLead or Admin closes with an explicit verdict, severity, and rationale. |
| `RETRY_AI` | `AWAITING_ANALYST`, `NEEDS_MANUAL_TRIAGE` | Starts a new pending attempt, resets retry counters, and enqueues after commit. The audit records a null final disposition. |

An explicit disposition includes a binary `final_verdict`, a `final_severity` of `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`, and a trimmed `rationale` of at least 10 characters. An action against an unavailable state returns HTTP 422. `CLOSED` is terminal. The alert status, decision audit row, and optional exemplar commit in one transaction under the alert row lock.

### Analytics and audit CSV

The summary returns `report_window` with the resolved inclusive UTC dates and rule. The browser uses this window for CSV export. `audit_event_count` counts every matching audit row, including escalations and retries. `total_closed` counts only closure actions. Agreement compares the verdict snapshots in those closure rows where both verdicts are binary. The override-rate denominator includes approvals and overrides. Current alert status, guardrail counts, and inference latency use alerts ingested during the window. Undefined metrics return `null`. The trend shows closure days and cumulative exemplar creation, including examples that have since been revoked. A day without approvals or overrides has no override rate.

### Evaluation

`POST /evaluation/run` compares the raw baseline and guarded pipeline over the synthetic input sets using the configured provider. Both modes run even if the client supplies the legacy `mode` query parameter. A mock run is a dry run. Missing cases or execution errors make the result inconclusive. `GET /evaluation/report` returns the last result held in process memory or JSON `null`, and the export endpoints return 404 until a result exists. Report and export reads do not start a run.

