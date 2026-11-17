"""Split Wazuh alerts.json exports into sample fixtures and report field coverage.

Usage:
    python backend/scripts/split_samples.py alerts_raw.jsonl backend/tests/fixtures/wazuh_samples
    python backend/scripts/split_samples.py alerts_raw.jsonl,fim_alerts.jsonl backend/tests/fixtures/wazuh_samples

The first argument may be one file or several files separated by commas.
"""
import json
import sys
from pathlib import Path

FIELDS = [
    "id", "timestamp", "rule.id", "rule.level", "rule.description", "rule.mitre",
    "agent.id", "agent.name", "agent.ip", "data.srcip", "full_log",
    "data.win.eventdata.image", "syscheck.path", "decoder.name",
]

# Very repetitive package-manager rules: keep only one sample of each.
NOISY_RULES = {"2901", "2902", "2904"}


def get(d, path):
    for key in path.split("."):
        if not isinstance(d, dict) or key not in d:
            return None
        d = d[key]
    return d


def load(sources: list[str]) -> list[dict]:
    alerts = []
    for src in sources:
        for line in Path(src).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                alerts.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return alerts


def main(src: str, outdir: str, limit: int = 12) -> None:
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    alerts = load([s.strip() for s in src.split(",") if s.strip()])

    per_rule: dict[str, int] = {}
    picked: list[dict] = []
    low_picked = False

    # Most important alerts first, so useful rules win the limited slots.
    for alert in sorted(alerts, key=lambda a: -(get(a, "rule.level") or 0)):
        rule_id = str(get(alert, "rule.id"))
        level = get(alert, "rule.level") or 0
        if level < 4:
            # keep one below-threshold alert for noise-filter tests (not dpkg noise)
            if not low_picked and rule_id not in NOISY_RULES:
                picked.append(alert)
                low_picked = True
            continue
        max_per_rule = 1  # one sample per rule gives the widest variety
        if per_rule.get(rule_id, 0) >= max_per_rule or len(picked) >= limit:
            continue
        per_rule[rule_id] = per_rule.get(rule_id, 0) + 1
        picked.append(alert)

    for i, alert in enumerate(picked, 1):
        name = f"sample_{i:02d}_rule{get(alert, 'rule.id')}_L{get(alert, 'rule.level')}.json"
        (out / name).write_text(json.dumps(alert, indent=2), encoding="utf-8")
        print("wrote", name)

    print(f"\nRead {len(alerts)} alerts, saved {len(picked)} samples.")
    print("\nField coverage (present in how many saved samples):")
    for f in FIELDS:
        n = sum(1 for a in picked if get(a, f) is not None)
        print(f"  {f:32} {n}/{len(picked)}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
