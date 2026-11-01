from __future__ import annotations

import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .database import sync_engine
from .routers import admin, alerts, analytics, auth, evaluation, governance

logger = logging.getLogger("sentrax.api")

app = FastAPI(
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:4173",
    ],
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


@app.get("/")
def root():
    return {
        "platform": "Sentra-X Copilot",
        "status": "OPERATIONAL",
        "version": "1.0.0",
        "documentation": "/docs",
    }


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

