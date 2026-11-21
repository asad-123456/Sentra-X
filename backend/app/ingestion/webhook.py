"""POST /api/webhooks/wazuh with header X-Sentrax-Signature: sha256=<hex>."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import asdict
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import SQLAlchemyError

from app.ingestion.db_access import get_session_factory
from app.ingestion.service import ingest_raws
from app.ingestion.wazuh_settings import get_wazuh_settings

router = APIRouter()
log = logging.getLogger("sentrax.ops.webhook")
MAX_WEBHOOK_BYTES = 1024 * 1024
MAX_WEBHOOK_ALERTS = 100


def verify_signature(secret: str, body: bytes | bytearray, header: Optional[str]) -> bool:
    if not secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    supplied = header[len("sha256="):]
    return supplied.isascii() and hmac.compare_digest(expected, supplied)


def _rejection(request_id: str, code: int, reason: str, detail: str) -> HTTPException:
    log.warning("webhook_rejected request_id=%s status=%d reason=%s", request_id, code, reason)
    return HTTPException(status_code=code, detail=detail, headers={"X-Request-ID": request_id})


@router.post("/api/webhooks/wazuh")
async def wazuh_webhook(
    request: Request,
    response: Response,
    x_sentrax_signature: Optional[str] = Header(default=None),
    factory=Depends(get_session_factory),
):
    request_id = uuid4().hex
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_WEBHOOK_BYTES:
            raise _rejection(request_id, 413, "body_too_large", "webhook body exceeds 1 MiB")
        body.extend(chunk)
    if not verify_signature(get_wazuh_settings().WAZUH_WEBHOOK_SECRET, body, x_sentrax_signature):
        raise _rejection(request_id, 401, "invalid_signature", "invalid signature")
    try:
        payload = json.loads(body)
    except ValueError:
        raise _rejection(request_id, 400, "invalid_json", "body is not valid JSON") from None
    raws = payload if isinstance(payload, list) else [payload]
    if len(raws) > MAX_WEBHOOK_ALERTS:
        raise _rejection(request_id, 413, "batch_too_large", "webhook batch exceeds 100 alerts")
    try:
        summary = await run_in_threadpool(ingest_raws, factory, raws)
    except SQLAlchemyError:
        raise _rejection(request_id, 503, "database_unavailable", "database unavailable") from None
    response.headers["X-Request-ID"] = request_id
    log.info("webhook_processed request_id=%s received=%d inserted=%d invalid=%d",
             request_id, summary.received, summary.inserted, summary.invalid)
    return asdict(summary)
