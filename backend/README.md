# Sentra-X backend

The FastAPI application ingests Wazuh events, runs guarded triage, serves the analyst workspace, and writes decisions to PostgreSQL. The route registry and lifespan are in [`app/main.py`](app/main.py). See the [backend and REST reference](../docs/backend_architecture_and_api_documentation.md) for the runtime flow and endpoint contracts.

## Local setup

Use Python 3.12 to match the container and PostgreSQL 16. From `backend/` in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Reuse the virtual environment if it is already set up. Copy the template only when creating a new `.env`. The Python requirements specify version ranges. In `backend/.env`:

- Point `DATABASE_URL` (`postgresql+psycopg://`) and `DATABASE_URL_ASYNC` (`postgresql+psycopg_async://`) to the intended PostgreSQL database.
- Set a unique `SECRET_KEY`. Generate one with `python -c "import secrets; print(secrets.token_hex(32))"`.
- Use `LLM_PROVIDER=mock` for routine development. Gemini and Claude require their corresponding keys. For local Ollama, see [Ollama triage](#ollama-triage). Use `DEMO_MODE=true` only for isolated demonstrations or tests that need it.
- Compose uses `backend/.env` by default. The loopback lab below uses its own `.env.lab`. Compose supplies the backend database URLs, `LLM_PROVIDER`, and `SEED_DEMO_DATA`.

Apply migrations to the intended database. Use the seed command only on a disposable demo database:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.seed_data
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Swagger is at `http://localhost:8000/docs`. The demo users are `analyst_01`, `teamlead_mercer`, and `admin_sys`. Their shared seed password is defined in [`app/seed_data.py`](app/seed_data.py) and is for a disposable demo only.

## Loopback Compose lab

Use Docker Desktop with Linux containers. From the repository root, create the ignored `.env.lab` once. Keep it with the lab volume because it contains the database password. The lab uses mock inference, requires sign-in, and seeds demo users when the database is empty. For a browser-only fixture demo, use the [frontend offline setup](../frontend/README.md#offline-mode).

```powershell
if (-not (Test-Path -LiteralPath .env.lab)) {
    @"
SENTRAX_BACKEND_ENV_FILE=.env.lab
SENTRAX_DB_PORT=15433
SENTRAX_API_PORT=18001
SENTRAX_HTTPS_PORT=18444
POSTGRES_PASSWORD=$([guid]::NewGuid().ToString('N'))
SECRET_KEY=$([guid]::NewGuid().ToString('N'))$([guid]::NewGuid().ToString('N'))
WAZUH_WEBHOOK_SECRET=$([guid]::NewGuid().ToString('N'))$([guid]::NewGuid().ToString('N'))
WAZUH_INGEST_MODE=webhook
DEMO_MODE=false
SEED_DEMO_DATA=true
LLM_PROVIDER=mock
"@ | Set-Content -LiteralPath .env.lab -Encoding ascii
}

docker compose --env-file .env.lab -p sentrax-lab up --build --wait
docker compose --env-file .env.lab -p sentrax-lab ps
docker compose --env-file .env.lab -p sentrax-lab exec -T db psql -U sentrax -d sentrax -Atc 'SELECT version_num FROM alembic_version'
curl.exe -fsS http://127.0.0.1:18001/api/health
curl.exe -fskS https://127.0.0.1:18444/api/health
```

Expect three healthy services, Alembic `0006_triage_generation`, and matching `HEALTHY` responses. Open `https://127.0.0.1:18444` and sign in as a seeded user. Nginx serves the browser and proxies `/api/` on the same origin. It uses a self-signed lab certificate. The direct API on port `18001` also serves `/docs`.

Compose reads `.env.lab` for substitutions and passes it to the backend. Keep `POSTGRES_PASSWORD`, `SECRET_KEY`, and `WAZUH_WEBHOOK_SECRET` set. Sign synthetic webhook requests using `WAZUH_WEBHOOK_SECRET` as described in the [source guide](../docs/wazuh_alert_source.md). The backend uses `postgresql+psycopg://sentrax:<password>@db:5432/sentrax` and `postgresql+psycopg_async://sentrax:<password>@db:5432/sentrax`. Host tools connect to `127.0.0.1:15433`. The three published ports bind to loopback. Keep `SEED_DEMO_DATA=true` for this seeded lab.

The Compose images use Python 3.12, PostgreSQL 16, Node 22 for the frontend build, and Nginx 1.27.

### Named accounts

For a fresh named-account lab, set `SEED_DEMO_DATA=false` and keep `DEMO_MODE=false` in the lab environment file before its first boot. Use a fresh Compose project and volume if you want to run it alongside the seeded lab. Give the second project unused host ports in its environment file.

After the services are healthy, run the bootstrap from an interactive terminal, using your lab's environment file and project name. For example:

```powershell
docker compose --env-file .env.named-lab -p sentrax-named-lab exec backend python -m scripts.bootstrap_admin ops-admin ops-admin@example.test
```

Enter and confirm a password at the hidden prompts. The command creates the first administrator and exits if an Admin account already exists. For a host-run backend, run `.\.venv\Scripts\python.exe -m scripts.bootstrap_admin <username> <email>` from `backend/` after migrating the configured database. Sign in with the new account and create the Analyst and TeamLead accounts in the Admin workspace's user management panel.

## Ingestion and triage

The Wazuh [source guide](../docs/wazuh_alert_source.md) covers configuration, the webhook contract and replay. The API lifespan starts the worker by default. The worker and Wazuh settings read `backend/.env` and the process environment. Use one API process for the in-process triage queue. `TRIAGE_ENABLED=false` disables consumption. On startup and periodically, the worker scans PostgreSQL for pending alerts, including work submitted by the standalone replay CLI.

In live mode, open **Admin & Benchmark → System Configuration** to see the running worker, its provider and model, and the effective ingestion and guardrail settings. Change the backend environment to update runtime settings. Recreate the backend container in Compose, or restart a backend running directly on the host, then select **Refresh settings**.

For a smoke test, start with an empty or newly populated disposable database and the mock provider. Ingest a fresh qualifying alert and verify `AWAITING_ANALYST`, an evidence pack, and an assessment. To test restart recovery, ingest another fresh alert with the worker disabled, then enable it and restart the API. The pending alert should reach the same state.

### Ollama triage

Run Ollama with cloud features disabled on the same machine as Sentra-X and install the local model with `ollama pull qwen3.5:4b`. For Docker Desktop, add these values to the lab environment file passed both to Compose and to the backend via `SENTRAX_BACKEND_ENV_FILE`.

```dotenv
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen3.5:4b
OLLAMA_TIMEOUT_SECONDS=90
TRIAGE_WORKERS=1
```

Use `http://127.0.0.1:11434` for a backend running directly on the host. Recreate the backend after changing its environment. The worker sends the existing sanitized evidence pack and any matching feedback exemplars to the local model. Sentra-X validates its structured reply, applies the triage rules, and sends unresolved provider failures to manual review. The Ollama timeout is per attempt and accommodates cold model loads. Keep the mock provider for routine tests.

## Testing and maintenance

Run `.\.venv\Scripts\python.exe -m pytest -rs` from `backend/`. Tests that need PostgreSQL skip unless their specific test URL is set in the process environment. Test database names must end in `_test`. Prepare these databases on a disposable PostgreSQL instance, such as the loopback Compose lab.

| Process variable | Database preparation and use |
| --- | --- |
| `SENTRAX_INTEGRATION_DATABASE_URL` | Migrate `sentrax_integration_test` to Alembic head. Analytics, webhook-to-worker, and opt-in benchmarks use it. |
| `SENTRAX_APP_TEST_DATABASE_URL` | Migrate and demo-seed `sentrax_app_test`. Older API and schema tests write persistent changes. Start with a fresh seeded database for each full run. Pytest derives both app URLs from this opt-in. |
| `SENTRAX_LEGACY_TEST_DATABASE_URL` | Create an empty `sentrax_legacy_test`. Ingestion, asset, auth, and exemplar suites create, truncate, and drop their own tables. |
| `TEST_DATABASE_URL` | Migrate `sentrax_triage_test` to Alembic head for the triage store and worker suites. |

For the analytics and smoke tests, create the database from the repository root and migrate it using the host Python environment. Use the [local setup](#local-setup) to install Python dependencies first.

```powershell
docker compose --env-file .env.lab -p sentrax-lab exec -T db createdb -U sentrax sentrax_integration_test
$labDbPassword = ((Get-Content -LiteralPath .env.lab | Where-Object { $_ -like 'POSTGRES_PASSWORD=*' }) -split '=', 2)[1]
$env:SENTRAX_INTEGRATION_DATABASE_URL = "postgresql+psycopg://sentrax:${labDbPassword}@127.0.0.1:15433/sentrax_integration_test"
$env:DATABASE_URL = $env:SENTRAX_INTEGRATION_DATABASE_URL
$env:DEMO_MODE = 'true'
Set-Location backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m pytest -rs tests/test_analytics.py -k 'not 50k'
.\.venv\Scripts\python.exe -m pytest -rs tests/test_e2e_stack.py
```

For all non-benchmark tests, set the four test URLs after the preparations above and run `.\.venv\Scripts\python.exe -m pytest -rs`. Set `DATABASE_URL` to the database being migrated before each `alembic upgrade head`. Before running `python -m app.seed_data` for `sentrax_app_test`, set both `DATABASE_URL` and `DATABASE_URL_ASYNC` to that database using the respective `postgresql+psycopg` and `postgresql+psycopg_async` drivers. Check skip reasons when verifying integration coverage. [`reset_db.py`](scripts/reset_db.py) and [`wipe_db.py`](scripts/wipe_db.py) remove data from the configured database and are for disposable environments.

Run the benchmarks individually against a freshly migrated `SENTRAX_INTEGRATION_DATABASE_URL`:

```powershell
$env:SENTRAX_RUN_PERF_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest -rs tests/test_analytics.py -k 50k
.\.venv\Scripts\python.exe -m pytest -rs tests/test_ingestion_load.py
```

The ingestion benchmark requires an empty alerts table. It feeds 3,000 alerts at five per second and reports the worker count, effective mock delay, observed backlog, and wall-clock triage latency. Set `MOCK_DELAY_MIN_SECONDS` and `MOCK_DELAY_MAX_SECONDS` to simulate inference time.

An admin starts an evaluation explicitly. Report reads return JSON `null` and exports return 404 until the first run. Reports live in API process memory. The benchmark identifies dry runs and marks runs with provider errors inconclusive.
