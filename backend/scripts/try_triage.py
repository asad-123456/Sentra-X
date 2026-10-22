"""Manual smoke check: one synthetic alert through assemble -> LLM -> guardrails.

Run from backend/:  python -m scripts.try_triage
Uses LLM_PROVIDER from .env (mock by default). The alert is synthetic.
"""
from datetime import datetime, timezone

from app.services.evidence_assembler import AlertRecord, assemble_evidence_pack
from app.services.llm_adapter import get_adapter, triage_alert
from app.services.rules_engine import apply_guardrails

alert = AlertRecord(
    wazuh_alert_id="demo-1",
    alert_timestamp=datetime.now(timezone.utc),
    rule_id="92052",
    rule_level=12,
    rule_description="PowerShell executed with encoded command",
    agent_id="001",
    agent_name="win-endpoint-01",
    src_ip="10.0.0.5",
    raw_payload={
        "rule": {"mitre": {"id": ["T1059.001"], "tactic": ["Execution"], "technique": ["PowerShell"]}},
        "data": {"win": {"eventdata": {"commandLine": "powershell.exe -NoP -W Hidden -Enc SQBFAFgA"}}},
        "full_log": "demo log line",
    },
)

ep = assemble_evidence_pack(alert, "HIGH")
adapter = get_adapter()
result = triage_alert(ep, adapter)

print(f"model={result.model_name} latency_ms={result.inference_latency_ms} "
      f"retries={result.retry_count} succeeded={result.succeeded}")
if result.last_error:
    print("last_error:", result.last_error)
if result.output:
    print("LLM output:", result.output.model_dump())
    print("Guardrails:", apply_guardrails(
        alert.rule_level, result.output, ep.valid_dot_keys, ep.injection_suspect))