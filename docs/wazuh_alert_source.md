# Wazuh alert source decision

Date: 2026-11-05

| Source | Result on our VM |
|---|---|
| Manager API :55000 `/alerts` | TBD (waiting for Abdur's curl output; expected to return an error) |
| Indexer :9200 `wazuh-alerts-*` | Installed (all-in-one), but listens only on 127.0.0.1, so not reachable from another machine |
| `/var/ossec/logs/alerts/alerts.json` | works (used for samples) |

## Decision
Primary ingest mode for the demo: **TBD (likely webhook)**
Reason: the indexer is not reachable from outside the manager VM (NAT networking), so polling it from Sentra-X will not work unless the network changes.

Tests always use **replay** mode with fixtures from `backend/tests/fixtures/wazuh_samples/`.

## Field notes for Abdur
- Present on all samples: id, timestamp, rule.id, rule.level, rule.description, agent.id, agent.name, agent.ip, decoder.name
- Sometimes missing: rule.mitre (rules 2902, 2904, 19003), data.srcip (only on SSH/PAM alerts, value 127.0.0.1), full_log (rule 19003)
- Never present on Ubuntu: data.win.eventdata.image
- FIM (syscheck.path): no samples yet
- Timestamp format: `YYYY-MM-DDTHH:MM:SS.mmm+0000`