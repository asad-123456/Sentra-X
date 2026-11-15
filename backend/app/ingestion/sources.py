"""Alert sources. Each one returns raw alert dicts; the parser does the rest."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Protocol

import httpx

log = logging.getLogger("sentrax.ingestion")


class AlertSource(Protocol):
    def fetch(self, cursor: Optional[datetime]) -> list[dict]: ...


class ReplaySource:
    """Reads a JSONL file (one alert per line). Used for tests and demos."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def fetch(self, cursor: Optional[datetime] = None) -> list[dict]:
        out: list[dict] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                log.warning("replay: skipping unparseable line")
        return out


class IndexerSource:
    """Polls the Wazuh indexer (OpenSearch) index wazuh-alerts-*."""

    def __init__(self, base_url: str, user: str, password: str,
                 verify_tls: bool = False, page_size: int = 1000):
        self.base_url = base_url.rstrip("/")
        self.page_size = page_size
        self._client = httpx.Client(auth=(user, password), verify=verify_tls, timeout=15.0)

    def fetch(self, cursor: Optional[datetime]) -> list[dict]:
        since = cursor or (datetime.now(timezone.utc) - timedelta(minutes=10))
        gte = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        body = {
            "size": self.page_size,
            "sort": [{"timestamp": {"order": "asc"}}],
            "query": {"range": {"timestamp": {"gte": gte}}},
        }
        r = self._client.post(f"{self.base_url}/wazuh-alerts-*/_search", json=body)
        r.raise_for_status()
        out: list[dict] = []
        for hit in r.json().get("hits", {}).get("hits", []):
            src = hit.get("_source") or {}
            if "id" not in src:  # fall back to the document id only if Wazuh left it out
                src = {**src, "id": hit["_id"]}
            out.append(src)
        return out
