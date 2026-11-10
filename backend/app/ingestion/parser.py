"""Pure parsing and filtering of raw Wazuh alerts (FR-1). No DB, no network."""
from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Optional

MAX_SIGNATURE_LEN = 512
SIGNATURE_PATHS = ("data.win.eventdata.image", "syscheck.path", "decoder.name")
_TS_FORMATS = ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z")
_WS = re.compile(r"\s+")


def get_path(data: Any, path: str) -> Any:
    """Read a dotted path like 'rule.mitre' from nested dicts. Returns None if absent."""
    cur = data
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def parse_timestamp(value: Any) -> datetime:
    """Wazuh timestamps look like 2026-10-22T10:15:30.123+0000. Returns UTC-aware datetime."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp missing")
    s = value.strip()
    dt: Optional[datetime] = None
    for fmt in _TS_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            break
        except ValueError:
            continue
    if dt is None:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))  # raises ValueError if bad
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_signature(value: Any) -> Optional[str]:
    """trim, collapse whitespace, lowercase, backslash -> slash, cap at 512 chars."""
    if not isinstance(value, str):
        return None
    s = _WS.sub(" ", value.strip()).lower().replace("\\", "/")
    s = s[:MAX_SIGNATURE_LEN].strip()
    return s or None


def extract_process_signature(raw: dict) -> Optional[str]:
    """First available of image, syscheck.path, decoder.name. NULL if none."""
    for path in SIGNATURE_PATHS:
        sig = normalize_signature(get_path(raw, path))
        if sig is not None:
            return sig
    return None


def _clean_ip(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


@dataclass(frozen=True)
class ParsedAlert:
    wazuh_alert_id: str
    rule_id: str
    rule_level: int
    rule_description: str
    agent_id: str
    agent_name: str
    agent_ip: Optional[str]
    src_ip: Optional[str]
    process_signature: Optional[str]
    raw_payload: dict
    alert_timestamp: datetime


@dataclass(frozen=True)
class ParseOutcome:
    status: Literal["accepted", "noise", "invalid"]
    alert: Optional[ParsedAlert] = None
    reason: Optional[str] = None


def parse_alert(raw: Any, min_level: int = 4) -> ParseOutcome:
    """Turn one raw alert dict into an outcome. Never raises, never mutates `raw`."""
    if not isinstance(raw, dict):
        return ParseOutcome("invalid", reason="alert is not an object")

    try:
        level = int(get_path(raw, "rule.level"))
    except (TypeError, ValueError):
        return ParseOutcome("invalid", reason="rule.level missing or not a number")
    if not 0 <= level <= 15:
        return ParseOutcome("invalid", reason=f"rule.level {level} outside 0-15")
    if level < min_level:
        return ParseOutcome("noise", reason=f"level {level} < {min_level}")

    alert_id = get_path(raw, "id")
    if alert_id is None or str(alert_id).strip() == "":
        return ParseOutcome("invalid", reason="id missing")
    rule_id = get_path(raw, "rule.id")
    if rule_id is None or str(rule_id).strip() == "":
        return ParseOutcome("invalid", reason="rule.id missing")
    agent_id = get_path(raw, "agent.id")
    if agent_id is None or str(agent_id).strip() == "":
        return ParseOutcome("invalid", reason="agent.id missing")
    try:
        ts = parse_timestamp(get_path(raw, "timestamp"))
    except ValueError:
        return ParseOutcome("invalid", reason="timestamp missing or unparseable")

    agent_id = str(agent_id).strip()
    agent_name = get_path(raw, "agent.name")
    alert = ParsedAlert(
        wazuh_alert_id=str(alert_id).strip(),
        rule_id=str(rule_id).strip(),
        rule_level=level,
        rule_description=str(get_path(raw, "rule.description") or ""),
        agent_id=agent_id,
        agent_name=str(agent_name).strip() if agent_name else agent_id,
        agent_ip=_clean_ip(get_path(raw, "agent.ip")),
        src_ip=_clean_ip(get_path(raw, "data.srcip")),
        process_signature=extract_process_signature(raw),
        raw_payload=raw,
        alert_timestamp=ts,
    )
    return ParseOutcome("accepted", alert=alert)