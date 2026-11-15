"""Pure parsing and filtering of raw Wazuh alerts (FR-1). No DB, no network."""
from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional

MAX_SIGNATURE_LEN = 512
# Column widths in the alerts table (Asad's schema). Longer values would make
# Postgres reject the whole batch, so such alerts are marked invalid instead.
MAX_ALERT_ID_LEN = 128
MAX_RULE_ID_LEN = 32
MAX_AGENT_ID_LEN = 64
MAX_AGENT_NAME_LEN = 255
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


def _str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if isinstance(v, (str, int)) and str(v).strip()]


def extract_mitre(raw: dict) -> tuple[list[str], list[str]]:
    """(tactics, technique ids) from rule.mitre. Empty lists when the rule has none."""
    mitre = get_path(raw, "rule.mitre")
    if not isinstance(mitre, dict):
        return [], []
    return _str_list(mitre.get("tactic")), _str_list(mitre.get("id"))


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
    mitre_tactics: list = field(default_factory=list)
    mitre_techniques: list = field(default_factory=list)


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

    alert_id = str(alert_id).strip()
    rule_id = str(rule_id).strip()
    agent_id = str(agent_id).strip()
    if len(alert_id) > MAX_ALERT_ID_LEN:
        return ParseOutcome("invalid", reason=f"id longer than {MAX_ALERT_ID_LEN} characters")
    if len(rule_id) > MAX_RULE_ID_LEN:
        return ParseOutcome("invalid", reason=f"rule.id longer than {MAX_RULE_ID_LEN} characters")
    if len(agent_id) > MAX_AGENT_ID_LEN:
        return ParseOutcome("invalid", reason=f"agent.id longer than {MAX_AGENT_ID_LEN} characters")

    agent_name = get_path(raw, "agent.name")
    agent_name = str(agent_name).strip()[:MAX_AGENT_NAME_LEN] if agent_name else agent_id
    tactics, techniques = extract_mitre(raw)
    alert = ParsedAlert(
        wazuh_alert_id=alert_id,
        rule_id=rule_id,
        rule_level=level,
        rule_description=str(get_path(raw, "rule.description") or ""),
        agent_id=agent_id,
        agent_name=agent_name or agent_id,
        agent_ip=_clean_ip(get_path(raw, "agent.ip")),
        src_ip=_clean_ip(get_path(raw, "data.srcip")),
        process_signature=extract_process_signature(raw),
        raw_payload=raw,
        alert_timestamp=ts,
        mitre_tactics=tactics,
        mitre_techniques=techniques,
    )
    return ParseOutcome("accepted", alert=alert)
