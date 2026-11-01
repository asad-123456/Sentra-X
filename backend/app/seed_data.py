from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any, Dict

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Add backend directory to path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import bcrypt
from sqlalchemy import text
from app.database import SyncSessionLocal

UUID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # DNS namespace


def hash_password(password: str) -> str:
    pwd_bytes = password[:72].encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def make_uuid(identifier: str) -> uuid.UUID:
    """Deterministically map string IDs (e.g. 'al-9021', 'usr-001') to stable UUIDs."""
    return uuid.uuid5(UUID_NAMESPACE, f"sentrax.{identifier}")


def seed_database():
    json_path = Path(__file__).resolve().parent / "demo_seed.json"
    if not json_path.exists():
        print(f"❌ Error: {json_path} does not exist.")
        return False

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("=" * 70)
    print("SENTRA-X DATABASE SEEDER (SRS v1.4 COMPLIANT SOC TELEMETRY)")
    print("=" * 70)

    password_hash = hash_password("sentrax2026")

    with SyncSessionLocal() as session:
        # 1. Seed Users
        print("\n[1/6] Seeding Users...")
        user_uuid_map = {}
        for u in data.get("users", []):
            u_id = make_uuid(u["id"])
            user_uuid_map[u["id"]] = u_id
            user_uuid_map[u["username"]] = u_id
            session.execute(
                text(
                    """
                    INSERT INTO users (id, username, email, password_hash, role, is_active, created_at)
                    VALUES (:id, :username, :email, :password_hash, :role, :is_active, :created_at)
                    ON CONFLICT (username) DO UPDATE
                    SET email = EXCLUDED.email,
                        role = EXCLUDED.role,
                        password_hash = EXCLUDED.password_hash;
                    """
                ),
                {
                    "id": u_id,
                    "username": u["username"],
                    "email": u["email"],
                    "password_hash": password_hash,
                    "role": u["role"],
                    "is_active": u.get("is_active", True),
                    "created_at": u.get("created_at", "2026-09-01T00:00:00Z"),
                },
            )
            print(f"  -> User: {u['username']} ({u['role']}) [UUID: {u_id}]")

        admin_id = user_uuid_map.get("admin_sys")
        teamlead_id = user_uuid_map.get("teamlead_mercer")

        # 2. Seed Assets
        print("\n[2/6] Seeding Assets (FR-9 Criticality Registry)...")
        asset_hostname_map = {}
        for asset in data.get("assets", []):
            asset_hostname_map[asset["agent_id"]] = asset["hostname"]
            session.execute(
                text(
                    """
                    INSERT INTO assets (agent_id, hostname, ip_address, criticality_tier, description, updated_by, created_at, updated_at)
                    VALUES (:agent_id, :hostname, :ip_address, :criticality_tier, :description, :updated_by, :created_at, :updated_at)
                    ON CONFLICT (agent_id) DO UPDATE
                    SET hostname = EXCLUDED.hostname,
                        ip_address = EXCLUDED.ip_address,
                        criticality_tier = EXCLUDED.criticality_tier,
                        description = EXCLUDED.description,
                        updated_by = EXCLUDED.updated_by,
                        updated_at = EXCLUDED.updated_at;
                    """
                ),
                {
                    "agent_id": asset["agent_id"],
                    "hostname": asset["hostname"],
                    "ip_address": asset["ip_address"],
                    "criticality_tier": asset["criticality_tier"],
                    "description": asset.get("description", ""),
                    "updated_by": admin_id,
                    "created_at": asset.get("created_at", "2026-09-01T08:00:00Z"),
                    "updated_at": asset.get("updated_at", "2026-10-10T14:30:00Z"),
                },
            )
            print(f"  -> Asset: {asset['agent_id']} | {asset['hostname']} ({asset['criticality_tier']})")

        # 3. Seed Feedback Exemplars
        print("\n[3/6] Seeding Feedback Exemplars (FR-4 Sub-50ms Index)...")
        for ex in data.get("exemplars", []):
            existing = session.execute(
                text(
                    "SELECT id FROM feedback_exemplars WHERE rule_id = :rule_id AND process_signature = :sig;"
                ),
                {"rule_id": ex["rule_id"], "sig": ex["process_signature"]},
            ).fetchone()

            if not existing:
                session.execute(
                    text(
                        """
                        INSERT INTO feedback_exemplars (
                            rule_id, process_signature, asset_criticality,
                            calibrated_verdict, calibrated_severity, rationale,
                            is_active, match_hit_count, user_id, created_by, created_at
                        ) VALUES (
                            :rule_id, :process_signature, :asset_criticality,
                            :calibrated_verdict, :calibrated_severity, :rationale,
                            :is_active, :match_hit_count, :user_id, :created_by, :created_at
                        );
                        """
                    ),
                    {
                        "rule_id": ex["rule_id"],
                        "process_signature": ex["process_signature"],
                        "asset_criticality": ex["asset_criticality"],
                        "calibrated_verdict": ex["calibrated_verdict"],
                        "calibrated_severity": ex["calibrated_severity"],
                        "rationale": ex["rationale"],
                        "is_active": ex.get("is_active", True),
                        "match_hit_count": ex.get("match_hit_count", 0),
                        "user_id": teamlead_id,
                        "created_by": teamlead_id,
                        "created_at": ex.get("created_at", "2026-09-14T15:20:00Z"),
                    },
                )
                print(f"  -> Exemplar: Rule {ex['rule_id']} [{ex['calibrated_verdict']}]")

        # 4. Seed Alerts
        print("\n[4/6] Seeding Ingested Alerts (FR-1, FR-5, SRS v1.4)...")
        alert_uuid_map = {}
        for a in data.get("alerts", []):
            a_id = make_uuid(a["id"])
            alert_uuid_map[a["id"]] = a_id
            host_name = a.get("agent_name", asset_hostname_map.get(a["agent_id"], "Unknown Host"))
            alert_ts = a.get("alert_timestamp", a.get("ingested_at", "2026-10-14T23:25:00Z"))

            session.execute(
                text(
                    """
                    INSERT INTO alerts (
                        id, wazuh_alert_id, rule_id, rule_level, rule_description,
                        agent_name, mitre_tactics, mitre_techniques, agent_id, src_ip,
                        process_signature, status, retry_count, alert_timestamp, ingested_at, updated_at
                    ) VALUES (
                        :id, :wazuh_alert_id, :rule_id, :rule_level, :rule_description,
                        :agent_name, CAST(:mitre_tactics AS jsonb), CAST(:mitre_techniques AS jsonb),
                        :agent_id, :src_ip, :process_signature, :status, :retry_count, :alert_timestamp, :ingested_at, :updated_at
                    )
                    ON CONFLICT (wazuh_alert_id) DO UPDATE
                    SET agent_name = EXCLUDED.agent_name,
                        status = EXCLUDED.status,
                        rule_level = EXCLUDED.rule_level,
                        retry_count = EXCLUDED.retry_count,
                        alert_timestamp = EXCLUDED.alert_timestamp,
                        updated_at = EXCLUDED.updated_at;
                    """
                ),
                {
                    "id": a_id,
                    "wazuh_alert_id": a["wazuh_alert_id"],
                    "rule_id": a["rule_id"],
                    "rule_level": a["rule_level"],
                    "rule_description": a["rule_description"],
                    "agent_name": host_name,
                    "mitre_tactics": json.dumps(a.get("mitre_tactics", [])),
                    "mitre_techniques": json.dumps(a.get("mitre_techniques", [])),
                    "agent_id": a["agent_id"],
                    "src_ip": a.get("src_ip"),
                    "process_signature": a.get("process_signature"),
                    "status": a.get("status", "PENDING_REVIEW"),
                    "retry_count": a.get("retry_count", 0),
                    "alert_timestamp": alert_ts,
                    "ingested_at": a.get("ingested_at", "2026-10-14T23:25:00Z"),
                    "updated_at": a.get("updated_at", "2026-10-14T23:25:08Z"),
                },
            )
            print(f"  -> Alert: {a['id']} | Wazuh {a['wazuh_alert_id']} | Host: {host_name} | L{a['rule_level']} ({a['status']})")

        # 5. Seed Evidence Packs & AI Assessments
        print("\n[5/6] Seeding Evidence Packs & AI Assessments (FR-2, FR-3)...")
        evidence_packs = data.get("evidencePacks", {})
        ai_assessments = data.get("aiAssessments", {})

        for a_str_id, ep in evidence_packs.items():
            if a_str_id not in alert_uuid_map:
                continue
            a_id = alert_uuid_map[a_str_id]
            ep_id = make_uuid(ep["id"])

            valid_keys = [
                "alert_metadata.rule.id",
                "alert_metadata.rule.level",
                "alert_metadata.rule.description",
                "telemetry_payload.data.win.eventdata.TargetImage",
                "telemetry_payload.data.win.eventdata.GrantedAccess",
                "telemetry_payload.data.win.eventdata.CommandLine",
                "telemetry_payload.data.win.eventdata.SourceImage",
                "telemetry_payload.full_log",
            ]

            session.execute(
                text(
                    """
                    INSERT INTO evidence_packs (
                        id, alert_id, pack_json, valid_dot_keys, injection_suspect,
                        injected_exemplar_ids, created_at, updated_at
                    ) VALUES (
                        :id, :alert_id, CAST(:pack_json AS jsonb), CAST(:valid_dot_keys AS jsonb),
                        :injection_suspect, CAST(:injected_exemplar_ids AS jsonb), :created_at, :updated_at
                    )
                    ON CONFLICT (alert_id) DO UPDATE
                    SET pack_json = EXCLUDED.pack_json,
                        valid_dot_keys = EXCLUDED.valid_dot_keys,
                        updated_at = EXCLUDED.updated_at;
                    """
                ),
                {
                    "id": ep_id,
                    "alert_id": a_id,
                    "pack_json": json.dumps(ep),
                    "valid_dot_keys": json.dumps(valid_keys),
                    "injection_suspect": ep.get("injection_suspect", False),
                    "injected_exemplar_ids": json.dumps(ep.get("injected_exemplar_ids", [])),
                    "created_at": ep.get("created_at", "2026-10-14T23:25:01Z"),
                    "updated_at": ep.get("created_at", "2026-10-14T23:25:01Z"),
                },
            )

        for a_str_id, ai in ai_assessments.items():
            if a_str_id not in alert_uuid_map:
                continue
            a_id = alert_uuid_map[a_str_id]
            ai_id = make_uuid(ai["id"])
            latency = ai.get("latency_ms", 1250)

            session.execute(
                text(
                    """
                    INSERT INTO ai_assessments (
                        id, alert_id, raw_verdict, raw_severity, effective_verdict,
                        effective_severity, confidence_score, cited_evidence_keys,
                        explanation, safety_floor_triggered, abstention_triggered,
                        guardrail_audit_note, llm_provider, model_name, latency_ms,
                        inference_latency_ms, retry_count, created_at, updated_at
                    ) VALUES (
                        :id, :alert_id, :raw_verdict, :raw_severity, :effective_verdict,
                        :effective_severity, :confidence_score, CAST(:cited_evidence_keys AS jsonb),
                        :explanation, :safety_floor_triggered, :abstention_triggered,
                        :guardrail_audit_note, :llm_provider, :model_name, :latency_ms,
                        :inference_latency_ms, :retry_count, :created_at, :updated_at
                    )
                    ON CONFLICT (alert_id) DO UPDATE
                    SET raw_verdict = EXCLUDED.raw_verdict,
                        effective_verdict = EXCLUDED.effective_verdict,
                        effective_severity = EXCLUDED.effective_severity,
                        confidence_score = EXCLUDED.confidence_score,
                        latency_ms = EXCLUDED.latency_ms,
                        inference_latency_ms = EXCLUDED.inference_latency_ms,
                        updated_at = EXCLUDED.updated_at;
                    """
                ),
                {
                    "id": ai_id,
                    "alert_id": a_id,
                    "raw_verdict": ai.get("raw_verdict", "TRUE_POSITIVE"),
                    "raw_severity": ai.get("raw_severity", "HIGH"),
                    "effective_verdict": ai.get("effective_verdict", "TRUE_POSITIVE"),
                    "effective_severity": ai.get("effective_severity", "HIGH"),
                    "confidence_score": ai.get("confidence_score", 0.95),
                    "cited_evidence_keys": json.dumps(ai.get("cited_evidence_keys", [])),
                    "explanation": ai.get("explanation", ""),
                    "safety_floor_triggered": ai.get("safety_floor_triggered", False),
                    "abstention_triggered": ai.get("abstention_triggered", False),
                    "guardrail_audit_note": ai.get("guardrail_audit_note"),
                    "llm_provider": ai.get("llm_provider", "Gemini"),
                    "model_name": ai.get("model_name", "gemini-2.5-flash"),
                    "latency_ms": latency,
                    "inference_latency_ms": latency,
                    "retry_count": ai.get("retry_count", 0),
                    "created_at": ai.get("created_at", "2026-10-14T23:25:05Z"),
                    "updated_at": ai.get("created_at", "2026-10-14T23:25:05Z"),
                },
            )
            print(f"  -> Evidence & Assessment linked for {a_str_id} (Effective: {ai.get('effective_verdict')}/{ai.get('effective_severity')})")

        # 6. Seed Historical Audit Records
        print("\n[6/6] Seeding Historical Audit Log (FR-6)...")
        default_user_id = user_uuid_map.get("analyst_01", list(user_uuid_map.values())[0])

        for aud in data.get("historicalAudit", []):
            a_str_id = aud.get("alert_id")
            if not a_str_id or a_str_id not in alert_uuid_map:
                continue
            a_id = alert_uuid_map[a_str_id]
            aud_id = make_uuid(aud["id"])

            existing_audit = session.execute(
                text("SELECT id FROM analyst_decisions_audit WHERE id = :id;"),
                {"id": aud_id},
            ).fetchone()

            if not existing_audit:
                session.execute(
                    text(
                        """
                        INSERT INTO analyst_decisions_audit (
                            id, alert_id, user_id, action_taken, previous_verdict,
                            previous_severity, final_verdict, final_severity,
                            rationale, exemplar_created, created_at
                        ) VALUES (
                            :id, :alert_id, :user_id, :action_taken, :previous_verdict,
                            :previous_severity, :final_verdict, :final_severity,
                            :rationale, :exemplar_created, :created_at
                        );
                        """
                    ),
                    {
                        "id": aud_id,
                        "alert_id": a_id,
                        "user_id": default_user_id,
                        "action_taken": aud.get("action_taken", "APPROVE"),
                        "previous_verdict": aud.get("previous_verdict"),
                        "previous_severity": aud.get("previous_severity"),
                        "final_verdict": aud.get("final_verdict"),
                        "final_severity": aud.get("final_severity"),
                        "rationale": aud.get("rationale", ""),
                        "exemplar_created": aud.get("exemplar_created", False),
                        "created_at": aud.get("created_at", "2026-10-14T23:30:00Z"),
                    },
                )
                print(f"  -> Audit Row: {aud['id']} for alert {a_str_id} [{aud.get('action_taken')}]")

        session.commit()

    print("\n" + "=" * 70)
    print("🎯 SENTRA-X DATABASE SEEDING COMPLETED WITH ZERO ERRORS!")
    print("=" * 70)
    return True


if __name__ == "__main__":
    seed_database()
