"""Generate replay fixtures (synthetic alerts) and optionally seed CLOSED alerts.

From the repo root:
  python backend\\scripts\\generate_replay.py                 # ac1_100, seq_100, stream_3000
  python backend\\scripts\\generate_replay.py --seed-closed 50000   # AC-14 data (needs the migrated database)
"""
from __future__ import annotations

import argparse
import copy
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

AGENTS = [("001", "ubuntu-1", "10.0.0.11"), ("002", "ubuntu-2", "10.0.0.12"), ("003", "ubuntu-3", "10.0.0.13")]
ATTACK_IPS = ["203.0.113.9", "198.51.100.23", "192.0.2.77", "185.220.101.4"]
USERS = ["root", "admin", "test", "oracle", "postgres"]

VALID = [
    dict(kind="ssh", rule_id="5710", level=5, desc="sshd: Attempt to login using a non-existent user",
         groups=["syslog", "sshd", "authentication_failed"], decoder="sshd", location="/var/log/auth.log",
         mitre=("T1110.001", "Credential Access", "Password Guessing")),
    dict(kind="pam", rule_id="5503", level=5, desc="PAM: User login failed.",
         groups=["syslog", "pam", "authentication_failed"], decoder="pam", location="/var/log/auth.log",
         mitre=("T1110", "Credential Access", "Brute Force")),
    dict(kind="fim", rule_id="550", level=7, desc="Integrity checksum changed.",
         groups=["ossec", "syscheck", "syscheck_entry_modified"], decoder="syscheck_integrity_changed",
         location="syscheck", mitre=("T1565.001", "Impact", "Stored Data Manipulation")),
    dict(kind="proc", rule_id="100001", level=10, desc="Suspicious command line executed (synthetic rule)",
         groups=["sysmon", "process_creation"], decoder="windows_eventchannel", location="EventChannel",
         mitre=("T1059", "Execution", "Command and Scripting Interpreter")),
    dict(kind="web", rule_id="31101", level=6, desc="Web server 400 error code.",
         groups=["web", "accesslog", "attack"], decoder="web-accesslog", location="/var/log/nginx/access.log",
         mitre=("T1190", "Initial Access", "Exploit Public-Facing Application")),
]
NOISE = [
    dict(kind="noise", rule_id="5402", level=3, desc="Successful sudo to ROOT executed.",
         groups=["syslog", "sudo"], decoder="sudo", location="/var/log/auth.log", mitre=None),
    dict(kind="noise", rule_id="1002", level=2, desc="Unknown problem somewhere in the system.",
         groups=["syslog", "errors"], decoder="syslog", location="/var/log/syslog", mitre=None),
]


def fmt_ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}+0000"


def build_alert(seq: int, ts: datetime, t: dict, rng: random.Random) -> dict:
    aid, name, ip = rng.choice(AGENTS)
    src = rng.choice(ATTACK_IPS)
    user = rng.choice(USERS)
    stamp = ts.strftime("%b %d %H:%M:%S")
    a = {
        "id": f"{int(ts.timestamp())}.{seq:07d}",
        "timestamp": fmt_ts(ts),
        "rule": {"id": t["rule_id"], "level": t["level"], "description": t["desc"],
                 "groups": t["groups"], "firedtimes": 1, "mail": False},
        "agent": {"id": aid, "name": name, "ip": ip},
        "manager": {"name": "wazuh-manager"},
        "decoder": {"name": t["decoder"]},
        "location": t["location"],
        "data": {},
        "full_log": "",
    }
    if t["mitre"]:
        mid, tactic, tech = t["mitre"]
        a["rule"]["mitre"] = {"id": [mid], "tactic": [tactic], "technique": [tech]}
    k = t["kind"]
    if k == "ssh":
        a["data"] = {"srcip": src, "srcuser": user}
        a["full_log"] = f"{stamp} {name} sshd[{rng.randint(1000, 9999)}]: Failed password for invalid user {user} from {src} port {rng.randint(20000, 60000)} ssh2"
    elif k == "pam":
        a["data"] = {"srcuser": user, "dstuser": "root"}
        a["full_log"] = f"{stamp} {name} sudo: pam_unix(sudo:auth): authentication failure; logname={user} uid=1000 euid=0 tty=/dev/pts/0 user={user}"
    elif k == "fim":
        path = f"/root/fimtest/file{rng.randint(1, 20)}.txt"
        a["syscheck"] = {"path": path, "event": "modified", "mode": "realtime"}
        a["full_log"] = f"File '{path}' modified"
    elif k == "proc":
        a["data"] = {"srcuser": user, "win": {"eventdata": {
            "image": "C:\\Windows\\System32\\cmd.exe",
            "commandLine": f"cmd.exe /c whoami && net user {user}"}}}
        a["full_log"] = f"Process created: cmd.exe /c whoami by {user}"
    elif k == "web":
        url = f"/index.php?id={rng.randint(1, 999)}'"
        a["data"] = {"srcip": src, "url": url, "id": "400"}
        a["full_log"] = f'{src} - - [{stamp}] "GET {url} HTTP/1.1" 400 150 "-" "curl/8.0"'
    else:
        a["full_log"] = f"{stamp} {name} {t['decoder']}: routine event"
    return a


def build_n(n, rng, templates, start, seq0=0, step=timedelta(seconds=1)):
    return [build_alert(seq0 + i, start + i * step, rng.choice(templates), rng) for i in range(n)]


def build_ac1(rng) -> list[dict]:
    """100 alerts: 70 valid, 20 below level 4, 10 repeated ids -> exactly 70 inserted."""
    start = datetime(2026, 10, 22, 10, 0, 0, tzinfo=timezone.utc)
    good = build_n(70, rng, VALID, start)
    noise = build_n(20, rng, NOISE, start, seq0=1000)
    repeats = [copy.deepcopy(good[i]) for i in range(10)]
    return good + noise + repeats


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    print(f"wrote {path} ({len(rows)} lines)")


def seed_closed(n: int, rng: random.Random) -> None:
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.ingestion.db_access import get_session_factory
    from app.ingestion.parser import parse_alert
    from app.ingestion.persistence import to_row
    from app.models import Alert, Asset

    now = datetime.now(timezone.utc)
    factory = get_session_factory()
    with factory.begin() as s:
        for aid, name, ip in AGENTS:
            s.execute(pg_insert(Asset).values(agent_id=aid, hostname=name, ip_address=ip)
                      .on_conflict_do_nothing(index_elements=["agent_id"]))
        for lo in range(0, n, 1000):
            rows = []
            for i in range(lo, min(lo + 1000, n)):
                raw = build_alert(i, now - timedelta(minutes=i + 1), rng.choice(VALID), rng)
                raw["id"] = f"seed.{i:07d}"
                parsed = parse_alert(raw, min_level=0).alert
                rows.append({**to_row(parsed), "status": "CLOSED"})
            s.execute(pg_insert(Alert).on_conflict_do_nothing(index_elements=["wazuh_alert_id"]), rows)
    print(f"seeded {n} CLOSED alerts")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="backend/tests/fixtures/replay")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--stream-count", type=int, default=3000)
    ap.add_argument("--seed-closed", type=int, default=0)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    out = Path(args.outdir)
    if args.seed_closed:
        seed_closed(args.seed_closed, rng)
        return
    t0 = datetime(2026, 10, 22, 10, 0, 0, tzinfo=timezone.utc)
    write_jsonl(out / "ac1_100.jsonl", build_ac1(rng))
    write_jsonl(out / "seq_100.jsonl", build_n(100, rng, VALID, t0, seq0=5000))
    write_jsonl(out / f"stream_{args.stream_count}.jsonl",
                build_n(args.stream_count, rng, VALID, t0, seq0=10000, step=timedelta(milliseconds=200)))


if __name__ == "__main__":
    main()
