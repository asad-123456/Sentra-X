"""POST /api/webhooks/wazuh with header X-Sentrax-Signature: sha256=<hex>."""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import SQLAlchemyError

from app.ingestion.db_access import get_session_factory
from app.ingestion.service import ingest_raws
from app.ingestion.wazuh_settings import get_wazuh_settings

router = APIRouter()


def verify_signature(secret: str, body: bytes, header: Optional[str]) -> bool:
    if not secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[len("sha256="):])


@router.post("/api/webhooks/wazuh")
async def wazuh_webhook(
    request: Request,
    x_sentrax_signature: Optional[str] = Header(default=None),
    factory=Depends(get_session_factory),
):
    body = await request.body()
    if not verify_signature(get_wazuh_settings().WAZUH_WEBHOOK_SECRET, body, x_sentrax_signature):
        raise HTTPException(status_code=401, detail="invalid signature")
    try:
        payload = json.loads(body)
    except ValueError:
        raise HTTPException(status_code=400, detail="body is not valid JSON")
    raws = payload if isinstance(payload, list) else [payload]
    try:
        summary = await run_in_threadpool(ingest_raws, factory, raws)
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="database unavailable")
    return asdict(summary)
