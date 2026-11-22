# Wazuh alert sources

| Mode | Configuration |
| --- | --- |
| `webhook` | Preferred for the lab described below. Configure the manager sender and `WAZUH_WEBHOOK_SECRET` in the selected backend environment file. |
| `poll` | Use a reachable HTTPS Wazuh Indexer with `WAZUH_INDEXER_URL`, credentials, and TLS verification appropriate to the deployment. The poller reads `wazuh-alerts-*`. |
| `replay` | Default development mode. Run the JSONL replay CLI with a fixture and target a disposable database. |

## Webhook

Send one JSON alert or a list of alerts to `POST /api/webhooks/wazuh`. The sender must provide `X-Sentrax-Signature: sha256=<hex>`, where the hex value is the HMAC-SHA256 of the exact request body using the shared secret. Configure the same secret at both ends. The endpoint is mounted independently of the ingest mode and verifies the signature on each request. Compose proxies the path through Nginx as well as exposing the API directly.

The endpoint accepts up to 1 MiB and 100 alerts per request. Larger requests return HTTP 413. Retrying a committed alert with the same Wazuh ID leaves one PostgreSQL alert.

### VirtualBox lab

Run the receiving lab with `SEED_DEMO_DATA=false` and [named accounts](../backend/README.md#named-accounts) before connecting a real manager. Wazuh agent IDs can overlap seeded asset IDs and inherit the corresponding demo hostname and tier.

The Compose backend, database, and UI stay on Windows loopback. A separate native Nginx listener binds to the Windows address that the manager VM can reach. Render the [gateway configuration template](../deploy/wazuh/nginx-windows.conf.template) with the laptop's interface IP, the manager VM's IP, the listener port, and the Compose backend's local port. The gateway allows the manager's source IP and forwards only the webhook POST. Install a server certificate for the listener IP or use a DNS name that the VM can resolve and verify. Configure the VM with a copy of the lab CA's public certificate. Keep the server key on Windows. [Nginx address restrictions](https://nginx.org/en/docs/http/ngx_http_access_module.html)

Before changing manager settings, send an unsigned POST from the manager with curl and the lab CA. HTTP 401 shows that the VM reached the webhook and validated TLS.

```sh
curl --cacert sentrax-ca.pem -sS -o /dev/null -w '%{http_code}\n' \
  --data '{}' 'https://HOST:PORT/api/webhooks/wazuh'
```

Install the [custom integration sender](../deploy/wazuh/custom-sentrax) as `/var/ossec/integrations/custom-sentrax` with owner `root:wazuh` and mode `0750`. Put the public CA at `/var/ossec/etc/sentrax-ca.pem`. Install the shared secret as `/var/ossec/etc/sentrax-webhook.secret` with owner `root:wazuh` and mode `0640`. Use a secure transfer for the secret and remove any staging copy from the manager after installation. The sender reads exact alert bytes, verifies TLS, and makes up to three total delivery attempts for transient network failures, 408, 429, and server errors. Wazuh retains the original alert for explicit redelivery if every attempt fails. [Wazuh custom integrations](https://documentation.wazuh.com/current/user-manual/manager/integration-with-external-apis.html)

Add the integration inside an existing `<ossec_config>` block on the manager. For the first validation, select a known harmless lab rule using its Wazuh rule ID. The custom sender reads the secret from its file.

```xml
<integration>
  <name>custom-sentrax</name>
  <hook_url>https://HOST:PORT/api/webhooks/wazuh</hook_url>
  <level>4</level>
  <rule_id>BENIGN_LAB_RULE_ID</rule_id>
  <alert_format>json</alert_format>
</integration>
```

Back up `ossec.conf`, check it with `/var/ossec/bin/wazuh-integratord -t`, and restart the manager after a successful check. Keep the receiving lab on mock inference. Follow the selected event ID from Wazuh to PostgreSQL and the analyst queue, then resend the same source event to verify deduplication. [Wazuh configuration validation](https://documentation.wazuh.com/current/user-manual/reference/ossec-conf/verifying-configuration.html)

To broaden forwarding, remove the `<rule_id>` line and any other alert filters from this integration, then validate and restart the manager. Wazuh forwards the alerts it generates. Sentra-X separately applies `WAZUH_MIN_LEVEL`, which defaults to 4. Set it to 0 in the receiving backend environment and recreate the backend to accept forwarded alerts at any valid level. Check ingestion counts and pending backlog when widening the feed. [Wazuh integration filters](https://documentation.wazuh.com/current/user-manual/reference/ossec-conf/integration.html)

### Start the existing Windows receiver

These commands apply to the configured VirtualBox workstation. For a new installation, use the [VirtualBox lab setup](#virtualbox-lab). Preserve the existing ignored `.env.m06-live` and use the `sentrax-m06-live` Compose project to reuse the database and its named accounts.

1. Start Docker Desktop. In Windows PowerShell, from the repository root, start the dedicated local Ollama server and then the stack.

   ```powershell
   docker info --format '{{.ServerVersion}}'
   & .\.agents\codex\private\start-sentrax-receiver-ollama.ps1
   docker compose --env-file .env.m06-live -p sentrax-m06-live config --quiet
   docker compose --env-file .env.m06-live -p sentrax-m06-live up -d --build --wait
   curl.exe -fskS https://127.0.0.1:18451/api/ready
   ```

2. Open [Sentra-X on port 18451](https://127.0.0.1:18451/queue), sign in with a named account, and verify **SIEM: webhook** and **LLM: ollama**. The UI serves saved alerts even before the separate Wazuh gateway is started.
3. Check the expected Windows address with `Get-NetIPAddress -IPAddress 192.168.100.57`. The existing gateway listens on that address, accepts the configured Wazuh manager, and forwards to the Compose backend on port `18007`. If the address has changed, review the gateway configuration, certificate, and manager webhook URL together before starting live delivery.

   ```powershell
   $gateway = (Resolve-Path '.env.m06-local\nginx-1.30.7').Path
   if (-not (Get-NetTCPConnection -LocalAddress 192.168.100.57 -LocalPort 18450 -State Listen -ErrorAction SilentlyContinue)) {
       & "$gateway\nginx.exe" -p "$gateway/" -c conf/sentrax-m06-live.conf -t
       if ($LASTEXITCODE -ne 0) { throw 'Wazuh gateway configuration check failed.' }
       Start-Process -FilePath "$gateway\nginx.exe" -WorkingDirectory $gateway `
           -ArgumentList @('-p', "$gateway/", '-c', 'conf/sentrax-m06-live.conf') -WindowStyle Hidden
       Start-Sleep -Seconds 1
   }
   Get-NetTCPConnection -LocalAddress 192.168.100.57 -LocalPort 18450 -State Listen
   ```

4. Start the manager and monitored VM in VirtualBox if needed. Inside each respective VM, check `sudo systemctl is-active wazuh-manager` and `sudo systemctl is-active wazuh-agent`. The acceptance setup forwards rule `533`. Confirm a fresh alert in the queue by its Wazuh ID and verify the saved model and evidence.

## Replay

From `backend/` with the API running against the same disposable database:

```powershell
.\.venv\Scripts\python.exe -m app.ingestion.replay tests/fixtures/replay/ac1_100.jsonl --rate 5
```

Replaying the same upstream alert ID does not create a second row. The worker recovers pending IDs written by the separate CLI from PostgreSQL.

## Lab observations from November 2026

The manager's port 55000 returned 404 for `/alerts` in the original lab. The indexer on port 9200 answered locally but listened on loopback, so the team chose webhook delivery. Confirm current reachability and TLS before choosing poll mode.

The [sample fixtures](../backend/tests/fixtures/wazuh_samples/) include Linux alerts and Windows file-integrity events. MITRE metadata, source IP, process details and full logs may be absent. Windows file-integrity events can identify a file through `syscheck.path`; the parser normalizes separators for process-signature matching. Typical sample timestamps use `YYYY-MM-DDTHH:MM:SS.mmm+0000`.
