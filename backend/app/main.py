from __future__ import annotations

import logging
from typing import Literal

from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .auth import require_roles
from .config import settings
from .database import sync_engine
from contextlib import asynccontextmanager

from .ingestion.db_access import get_session_factory
from .ingestion.poller import Poller
from .ingestion.sources import IndexerSource
from .ingestion.wazuh_settings import get_wazuh_settings
from .ingestion.webhook import router as webhook_router
from .routers import admin, alerts, analytics, auth, evaluation, governance
from .services.evidence_assembler import MAX_EXEMPLARS
from .services.rules_engine import MIN_CONFIDENCE
from .worker.triage_worker import start_worker, stop_worker
from .worker.worker_settings import get_worker_settings

logger = logging.getLogger("sentrax.api")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run the triage worker and the optional Wazuh poller with the API."""
    w = get_wazuh_settings()
    poller = None
    if w.WAZUH_INGEST_MODE == "poll":
        poller = Poller(
            IndexerSource(w.WAZUH_INDEXER_URL, w.WAZUH_INDEXER_USER,
                          w.WAZUH_INDEXER_PASSWORD, w.WAZUH_VERIFY_TLS),
            get_session_factory(), w.WAZUH_POLL_INTERVAL_SECONDS, w.WAZUH_MIN_LEVEL,
        )
    try:
        app.state.triage_worker = start_worker()
        if poller:
            poller.start()
        yield
    finally:
        try:
            if poller:
                poller.stop()
        finally:
            stop_worker()
            app.state.triage_worker = None


app = FastAPI(
    lifespan=lifespan,
    title="Sentra-X Security Operations Workspace API",
    version="1.0.0",
    description="Evidence-Grounded and Uncertainty-Aware Human-in-the-Loop SOC Alert Triage Copilot API",
)

@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error("Unhandled database error during %s %s: %s", request.method, request.url.path, str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal database error. The database transaction was rolled back."},
    )

# Configure CORS for Frontend Vite Dev Server
allowed_origins = [
    origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",") if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all API routers under /api/v1
app.include_router(auth.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(governance.router, prefix="/api/v1")
app.include_router(evaluation.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
# NOTE: The Wazuh webhook is intentionally mounted at /api/webhooks/wazuh (no /v1 prefix).
# This matches the path documented in docs/wazuh_alert_source.md and configured in
# the Wazuh server's integration block. Do NOT move it under /api/v1 without updating
# both the Wazuh integration config and nginx.conf.
app.include_router(webhook_router)  # POST /api/webhooks/wazuh


@app.get("/")
def root():
    return {
        "platform": "Sentra-X Copilot",
        "status": "OPERATIONAL",
        "version": "1.0.0",
        "documentation": "/docs",
    }


class RuntimeSettings(BaseModel):
    ingestion_mode: Literal["poll", "webhook", "replay", "unknown"]
    min_rule_level: int
    polling_interval_seconds: int | None
    worker_status: Literal["running", "disabled", "stopped"]
    active_workers: int
    llm_provider: str | None
    model_name: str | None
    abstention_threshold: float
    max_exemplars_injected: int


@app.get(
    "/api/v1/runtime/settings",
    dependencies=[Depends(require_roles("Analyst", "TeamLead", "Admin"))],
)
def get_runtime_settings(request: Request) -> RuntimeSettings:
    """Report process settings and worker threads without probing external services."""
    wazuh = get_wazuh_settings()
    mode = wazuh.WAZUH_INGEST_MODE
    worker = getattr(request.app.state, "triage_worker", None)
    active_workers = worker.active_workers if worker is not None else 0
    if active_workers:
        worker_status = "running"
    elif not get_worker_settings().TRIAGE_ENABLED:
        worker_status = "disabled"
    else:
        worker_status = "stopped"

    return RuntimeSettings(
        ingestion_mode=mode if mode in {"poll", "webhook", "replay"} else "unknown",
        min_rule_level=wazuh.WAZUH_MIN_LEVEL,
        polling_interval_seconds=wazuh.WAZUH_POLL_INTERVAL_SECONDS if mode == "poll" else None,
        worker_status=worker_status,
        active_workers=active_workers,
        llm_provider=worker.provider_name if active_workers else None,
        model_name=worker.model_name if active_workers else None,
        abstention_threshold=MIN_CONFIDENCE,
        max_exemplars_injected=MAX_EXEMPLARS,
    )


@app.get("/api/health")
def health_check():
    db_status = "CONNECTED"
    db_engine = "PostgreSQL"
    try:
        with sync_engine.connect() as conn:
            raw_ver = conn.execute(text("SELECT version()")).scalar()
            if raw_ver:
                db_engine = raw_ver.split(",")[0].strip()
    except Exception as exc:
        db_status = f"DISCONNECTED: {exc}"

    is_healthy = db_status == "CONNECTED"
    return {
        "status": "HEALTHY" if is_healthy else "DEGRADED",
        "database": db_status,
        "engine": db_engine,
    }

