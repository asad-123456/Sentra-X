"""Builds the EvidencePack JSON for an alert (FR-2).

Pure functions, no database access. Part 6 converts ORM rows into the two
dataclasses below and persists the returned EvidencePack.

dot-key convention (tell the frontend, put it in the Design Document):
  - nested objects use dots:            alert_metadata.rule.id
  - a non-empty list of plain values
    is ONE citable key:                 alert_metadata.rule.mitre.id
  - a list containing objects uses
    bracket indexes:                    temporal_context[0].rule_id
  - only leaf values are citable; None and "" are not.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

from app.services.prompt_sanitizer import sanitize_value

# Config constants (SRS: env/config values, not DB rows).
MAX_CORRELATED = 5                      # K
CORRELATION_WINDOW = timedelta(hours=24)  # W
MAX_EXEMPLARS = 2
DEFAULT_CRITICALITY = "MEDIUM"          # Atta auto-registers unseen agents as MEDIUM


@dataclass(frozen=True)
class AlertRecord:
    """The alert being triaged (mirrors the `alerts` table columns we need)."""

    wazuh_alert_id: str
    alert_timestamp: datetime
    rule_id: str
    rule_level: int
    rule_description: str
    agent_id: str
    agent_name: str
    src_ip: str | None = None
    process_signature: str | None = None
    raw_payload: dict = field(default_factory=dict)


@dataclass(frozen=True)
class CorrelatedAlert:
    """A candidate earlier alert, used for temporal context."""

    wazuh_alert_id: str
    alert_timestamp: datetime
    rule_id: str
    rule_level: int
    rule_description: str
    agent_id: str | None = None
    src_ip: str | None = None


@dataclass
class EvidencePack:
    pack: dict                      # -> evidence_packs.pack_json
    valid_dot_keys: list[str]       # -> evidence_packs.valid_dot_keys
    injection_suspect: bool         # -> evidence_packs.injection_suspect
    injected_exemplar_ids: list[int]  # -> evidence_packs.injected_exemplar_ids
    findings: list[str] = field(default_factory=list)  # logging/debug only


# --- helpers ----------------------------------------------------------------
def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso(dt: datetime) -> str:
    return _as_utc(dt).isoformat()


def _is_scalar(v: Any) -> bool:
    return isinstance(v, (str, int, float, bool))


def collect_dot_keys(value: Any, prefix: str = "") -> list[str]:
    """Return every citable key path inside `value` (see module docstring)."""
    keys: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            path = f"{prefix}.{k}" if prefix else str(k)
            keys.extend(collect_dot_keys(v, path))
    elif isinstance(value, list):
        if value and all(_is_scalar(i) for i in value):
            keys.append(prefix)
        else:
            for i, item in enumerate(value):
                keys.extend(collect_dot_keys(item, f"{prefix}[{i}]"))
    elif value is None or value == "":
        pass
    else:
        keys.append(prefix)
    return keys


_TOKEN = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


def resolve_dot_key(pack: Any, key: str) -> Any:
    """Look a dot key up in a pack. Raises KeyError if it doesn't exist."""
    cur = pack
    for name, index in _TOKEN.findall(key):
        if name:
            if not isinstance(cur, dict) or name not in cur:
                raise KeyError(key)
            cur = cur[name]
        else:
            i = int(index)
            if not isinstance(cur, list) or i >= len(cur):
                raise KeyError(key)
            cur = cur[i]
    return cur


_UNSAFE_KEY_CHARS = re.compile(r"[.\[\]]")


def _neutralize_keys(value: Any) -> Any:
    """Replace '.', '[' and ']' inside dict keys so dot paths stay unambiguous.
    (If two keys collide after this, the later one wins. Unlikely in practice.)"""
    if isinstance(value, dict):
        return {
            _UNSAFE_KEY_CHARS.sub("_", str(k)): _neutralize_keys(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_neutralize_keys(i) for i in value]
    return value


# --- correlation ------------------------------------------------------------
def select_correlated(
    alert: AlertRecord,
    candidates: Sequence[CorrelatedAlert],
    k: int = MAX_CORRELATED,
    window: timedelta = CORRELATION_WINDOW,
) -> list[CorrelatedAlert]:
    """Up to k earlier alerts with the same agent_id or src_ip inside the window,
    most recent first. The alert itself is excluded."""
    ref = _as_utc(alert.alert_timestamp)
    earliest = ref - window
    matches: list[tuple[datetime, CorrelatedAlert]] = []
    for c in candidates:
        if c.wazuh_alert_id == alert.wazuh_alert_id:
            continue
        ts = _as_utc(c.alert_timestamp)
        if not (earliest <= ts <= ref):
            continue
        same_agent = c.agent_id is not None and c.agent_id == alert.agent_id
        same_ip = c.src_ip is not None and c.src_ip == alert.src_ip
        if same_agent or same_ip:
            matches.append((ts, c))
    matches.sort(key=lambda pair: pair[0], reverse=True)
    return [c for _, c in matches[:k]]


def _summarize(c: CorrelatedAlert, ref: datetime) -> dict:
    ts = _as_utc(c.alert_timestamp)
    summary = {
        "wazuh_alert_id": c.wazuh_alert_id,
        "timestamp": _iso(ts),
        "minutes_before": int((ref - ts).total_seconds() // 60),
        "rule_id": str(c.rule_id),
        "rule_level": c.rule_level,
        "rule_description": c.rule_description,
        "agent_id": c.agent_id,
        "src_ip": c.src_ip,
    }
    return {k: v for k, v in summary.items() if v is not None}


# --- raw payload extraction -------------------------------------------------
def _mitre(raw: dict) -> dict:
    rule = raw.get("rule")
    mitre = rule.get("mitre") if isinstance(rule, dict) else None
    if not isinstance(mitre, dict):
        return {}
    out: dict[str, list[str]] = {}
    for key in ("id", "tactic", "technique"):
        v = mitre.get(key)
        if v is None:
            continue
        items = v if isinstance(v, list) else [v]
        items = [str(i) for i in items if i not in (None, "")]
        if items:
            out[key] = items
    return out


def _telemetry(raw: dict) -> dict:
    out: dict[str, Any] = {}
    for key in ("data", "syscheck"):
        v = raw.get(key)
        if isinstance(v, dict) and v:
            out[key] = v
    full_log = raw.get("full_log")
    if isinstance(full_log, str) and full_log:
        out["full_log"] = full_log
    return out


# --- main entry point -------------------------------------------------------
def assemble_evidence_pack(
    alert: AlertRecord,
    criticality_tier: str | None,
    candidate_alerts: Sequence[CorrelatedAlert] = (),
    exemplar_ids: Sequence[int] = (),
    k: int = MAX_CORRELATED,
    window: timedelta = CORRELATION_WINDOW,
) -> EvidencePack:
    raw = alert.raw_payload if isinstance(alert.raw_payload, dict) else {}
    ref = _as_utc(alert.alert_timestamp)

    correlated = select_correlated(alert, candidate_alerts, k=k, window=window)

    unsanitized = {
        "alert_metadata": {
            "wazuh_alert_id": alert.wazuh_alert_id,
            "timestamp": _iso(alert.alert_timestamp),
            "rule": {
                "id": str(alert.rule_id),
                "level": alert.rule_level,
                "description": alert.rule_description,
                "mitre": _mitre(raw),
            },
        },
        "asset_context": {
            "agent_id": alert.agent_id,
            "agent_name": alert.agent_name,
            "criticality_tier": criticality_tier or DEFAULT_CRITICALITY,
        },
        "telemetry_payload": _telemetry(raw),
        "temporal_context": [_summarize(c, ref) for c in correlated],
    }

    result = sanitize_value(unsanitized)
    pack = _neutralize_keys(result.value)
    valid_keys = sorted(set(collect_dot_keys(pack)))

    return EvidencePack(
        pack=pack,
        valid_dot_keys=valid_keys,
        injection_suspect=result.injection_suspect,
        injected_exemplar_ids=list(exemplar_ids)[:MAX_EXEMPLARS],
        findings=result.findings,
    )