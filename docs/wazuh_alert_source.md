# Wazuh alert source decision

Date: 2026-11-05 (updated 2026-11-17)

| Source | Result on our VM |
|---|---|
| Manager API :55000 `/alerts` | **404 Not Found** (confirmed by Abdur on 2026-11-16). The Wazuh API cannot serve alerts. |
| Indexer :9200 `wazuh-alerts-*` | Works on the manager itself (6,928 alerts, `sort=timestamp:desc` works), but listens only on 127.0.0.1, so not reachable from another machine |
| `/var/ossec/logs/alerts/alerts.json` | works (used for samples) |

## Decision
Primary ingest mode for the demo: **webhook** (HMAC-signed push from the manager to `POST /api/webhooks/wazuh`).
Reason: the Manager API cannot serve alerts, and the indexer is not reachable from outside the manager VM (NAT networking), so polling it from Sentra-X will not work unless the network changes.

Alternative: if Abdur opens port 9200 to the backend host, set `WAZUH_INGEST_MODE=poll` and the poller reads the indexer (`wazuh-alerts-*`, sorted by timestamp). Open question sent to Abdur on 2026-11-17.

Tests always use **replay** mode with fixtures from `backend/tests/fixtures/wazuh_samples/`.

## Field notes for Abdur
- Present on all samples: id, timestamp, rule.id, rule.level, rule.description, agent.id, agent.name, agent.ip, decoder.name
- Sometimes missing: rule.mitre (rules 2902, 2904, 19003, 554), data.srcip (only on SSH/PAM alerts, value 127.0.0.1; absent on FIM alerts), full_log (rule 19003)
- Never present on Ubuntu: data.win.eventdata.image
- FIM (syscheck.path): samples now available from a Windows 11 agent (agent 006, Windows-PC, 172.16.16.199), monitoring `C:\fimtest` in real time:
  - rule 554, level 5, file added
  - rule 550, level 7, integrity checksum changed (has rule.mitre T1565.001)
  - rule 553, level 7, file deleted (has rule.mitre T1070.004, T1485)
  - `syscheck.path` uses Windows paths (e.g. `c:\fimtest\test1.txt`); the parser normalises backslashes to forward slashes for `process_signature`
- Timestamp format: `YYYY-MM-DDTHH:MM:SS.mmm+0000`