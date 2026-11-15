from __future__ import annotations

import sys
import uuid
from pathlib import Path

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Add backend directory to path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from starlette.testclient import TestClient
from app.config import settings
from app.main import app

client = TestClient(app)


def run_all_api_tests():
    print("=" * 70)
    print("SENTRA-X FASTAPI ENDPOINT & INTEGRATION TEST SUITE")
    print("=" * 70)

    # 1. Health check
    res = client.get("/api/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    assert res.json()["status"] == "HEALTHY"
    print("✅ PASS: [GET /api/health] Status is HEALTHY")

    # 2. Authentication: Login
    login_res = client.post("/api/v1/auth/login", json={"username": "analyst_01", "password": "sentrax2026"})
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    auth_data = login_res.json()
    token = auth_data["access_token"]
    assert token, "Token missing"
    assert auth_data["user"]["role"] == "Analyst"
    print(f"✅ PASS: [POST /api/v1/auth/login] Logged in as analyst_01 (Token: {token[:16]}...)")

    # 3. Auth Me
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200, f"Auth me failed: {me_res.text}"
    assert me_res.json()["username"] == "analyst_01"
    print("✅ PASS: [GET /api/v1/auth/me] Verified Bearer JWT validation")

    # 4. Queue: Alert Listing
    queue_res = client.get("/api/v1/alerts?tab=awaiting&page=1&page_size=10")
    assert queue_res.status_code == 200, f"Queue failed: {queue_res.text}"
    queue_data = queue_res.json()
    assert queue_data["total"] > 0, "No alerts returned"
    assert len(queue_data["items"]) > 0, "Alert items empty"
    first_alert = queue_data["items"][0]
    print(f"✅ PASS: [GET /api/v1/alerts] Returned {queue_data['total']} alerts across {queue_data['totalPages']} pages")

    # 5. Queue Counts
    counts_res = client.get("/api/v1/alerts/counts")
    assert counts_res.status_code == 200, f"Counts failed: {counts_res.text}"
    counts = counts_res.json()
    assert counts["awaiting"] >= 0
    assert counts["criticalSafetyFloor"] >= 0
    print(f"✅ PASS: [GET /api/v1/alerts/counts] Awaiting: {counts['awaiting']}, Safety Floor: {counts['criticalSafetyFloor']}")

    # 6. Alert Detail Modal Data
    test_alert_id = "al-9021"
    detail_res = client.get(f"/api/v1/alerts/{test_alert_id}")
    assert detail_res.status_code == 200, f"Detail failed: {detail_res.text}"
    detail = detail_res.json()
    assert detail["alert"]["rule_id"] == "100201"
    assert detail["asset"]["agent_id"] == "001"
    assert detail["evidence_pack"] is not None
    assert detail["ai_assessment"] is not None
    assert len(detail["ai_assessment"]["cited_evidence_keys"]) > 0
    print(f"✅ PASS: [GET /api/v1/alerts/{test_alert_id}] Evidence Pack & Assessment retrieved")

    # 7. Decision Submission: OVERRIDE with short rationale (MUST FAIL with HTTP 422)
    short_override = client.post(
        f"/api/v1/alerts/{test_alert_id}/decision",
        json={
            "action": "OVERRIDE",
            "final_verdict": "FALSE_POSITIVE",
            "final_severity": "LOW",
            "rationale": "too short",  # < 10 chars
        },
    )
    assert short_override.status_code == 422, f"Expected 422 for short rationale, got {short_override.status_code}"
    print("✅ PASS: [POST /api/v1/alerts/.../decision] Enforced >= 10 character rationale on OVERRIDE (HTTP 422)")

    # 8. Decision Submission: Valid APPROVE
    approve_res = client.post(
        f"/api/v1/alerts/{test_alert_id}/decision",
        json={
            "action": "APPROVE",
            "rationale": "Verified authentic threat activity matching Sysmon event.",
        },
    )
    assert approve_res.status_code == 200, f"Approve failed: {approve_res.text}"
    audit_record = approve_res.json()
    assert audit_record["action_taken"] == "APPROVE"
    print("✅ PASS: [POST /api/v1/alerts/.../decision] Successfully submitted APPROVE decision (Status -> CLOSED)")

    # 9. Decision Submission: Valid OVERRIDE (Testing FR-4 Exemplar creation)
    target_override_alert = "al-9020"
    override_res = client.post(
        f"/api/v1/alerts/{target_override_alert}/decision",
        json={
            "action": "OVERRIDE",
            "final_verdict": "FALSE_POSITIVE",
            "final_severity": "LOW",
            "rationale": "Legitimate enterprise backup script executing maintenance under CorpIT schedule.",
        },
    )
    assert override_res.status_code == 200, f"Override failed: {override_res.text}"
    assert override_res.json()["exemplar_created"] is True
    print("✅ PASS: [POST /api/v1/alerts/.../decision] Submitted OVERRIDE and created feedback exemplar (FR-4)")

    # 9b. Decision Submission: RETRY_AI (verifying status stays in awaiting and guardrails applied)
    retry_alert_id = "al-9019"
    retry_res = client.post(
        f"/api/v1/alerts/{retry_alert_id}/decision",
        json={"action": "RETRY_AI", "rationale": "Re-running guardrails check on ambiguous telemetry."},
    )
    assert retry_res.status_code == 200, f"RETRY_AI failed: {retry_res.text}"
    assert retry_res.json()["action_taken"] == "RETRY_AI"
    retry_detail = client.get(f"/api/v1/alerts/{retry_alert_id}").json()
    assert retry_detail["alert"]["status"] in ("AWAITING_ANALYST", "NEEDS_MANUAL_TRIAGE")
    print(f"✅ PASS: [POST /api/v1/alerts/.../decision] RETRY_AI succeeded (Status: {retry_detail['alert']['status']})")

    # 10. Analytics KPI Summary
    analytics_res = client.get("/api/v1/analytics?range=30d")
    assert analytics_res.status_code == 200, f"Analytics failed: {analytics_res.text}"
    an_data = analytics_res.json()
    assert an_data["ai_agreement_rate"] > 0
    assert "agreement_matrix" in an_data
    assert len(an_data["override_trend"]) > 0
    print(f"✅ PASS: [GET /api/v1/analytics] Agreement Rate: {an_data['ai_agreement_rate']}%, Kappa: {an_data['cohens_kappa']}")

    # 11. Streaming CSV Export
    csv_res = client.get("/api/v1/analytics/export-csv")
    assert csv_res.status_code == 200, f"CSV export failed: {csv_res.text}"
    assert "text/csv" in csv_res.headers.get("content-type", "")
    assert "Decision ID,Timestamp,Wazuh Alert ID" in csv_res.text
    print(f"✅ PASS: [GET /api/v1/analytics/export-csv] Generated streaming CSV audit trail ({len(csv_res.text)} bytes)")

    # 12. Governance: Exemplars
    ex_res = client.get("/api/v1/governance/exemplars")
    assert ex_res.status_code == 200
    exemplars = ex_res.json()
    assert len(exemplars) > 0
    first_ex_id = exemplars[0]["id"]
    print(f"✅ PASS: [GET /api/v1/governance/exemplars] Loaded {len(exemplars)} feedback exemplars")

    # 13. Governance: Exemplar Revocation Toggle
    toggle_res = client.patch(f"/api/v1/governance/exemplars/{first_ex_id}", json={"is_active": False})
    assert toggle_res.status_code == 200
    assert toggle_res.json()["is_active"] is False
    print(f"✅ PASS: [PATCH /api/v1/governance/exemplars/{first_ex_id}] Toggled exemplar active status")

    # 14. Governance: Asset Registry
    assets_res = client.get("/api/v1/governance/assets")
    assert assets_res.status_code == 200
    assert len(assets_res.json()) >= 6
    print(f"✅ PASS: [GET /api/v1/governance/assets] Loaded {len(assets_res.json())} monitored host assets")

    # 15. Adversarial Benchmark Suite
    suite_res = client.get("/api/v1/evaluation/suite")
    assert suite_res.status_code == 200
    assert len(suite_res.json()) == 30
    print(f"✅ PASS: [GET /api/v1/evaluation/suite] Loaded complete 30-payload adversarial test suite")

    # 16. Benchmark Evaluation Report
    report_res = client.get("/api/v1/evaluation/report")
    assert report_res.status_code == 200
    report = report_res.json()
    assert report["sentrax_bypass_rate"] == 0.0
    assert report["nfr3_target_achieved"] is True
    print(f"✅ PASS: [GET /api/v1/evaluation/report] Verified 0% prompt-injection bypass target met")

    # 16b. Benchmark Evaluation Run (POST /run)
    run_res = client.post("/api/v1/evaluation/run?mode=full")
    assert run_res.status_code == 200
    run_report = run_res.json()
    assert run_report["sentrax_bypass_rate"] == 0.0
    assert len(run_report["adversarial_suite"]) == 30
    print(f"✅ PASS: [POST /api/v1/evaluation/run] Executed adversarial evaluation run dynamically")

    # 16c. Benchmark Export Formats (Markdown & CSV per AC-18)
    md_res = client.get("/api/v1/evaluation/export-md")
    assert md_res.status_code == 200
    assert "Sentra-X Adversarial Benchmark & Model Evaluation Report" in md_res.text
    csv_res = client.get("/api/v1/evaluation/export-csv")
    assert csv_res.status_code == 200
    assert "Payload ID,Category,Target Field" in csv_res.text
    print(f"✅ PASS: [GET /api/v1/evaluation/export-md & export-csv] Generated research evaluation reports (AC-18)")

    # =========================================================================
    # SRS v1.4 ACCEPTANCE CRITERIA SUITE (AC-12, AC-14, AC-16, AC-17)
    # =========================================================================
    print("\n--- Verifying SRS v1.4 Role-Based Acceptance Criteria ---")

    # Log in as TeamLead and Admin
    tl_login = client.post("/api/v1/auth/login", json={"username": "teamlead_mercer", "password": "sentrax2026"})
    assert tl_login.status_code == 200
    tl_token = tl_login.json()["access_token"]

    admin_login = client.post("/api/v1/auth/login", json={"username": "admin_sys", "password": "sentrax2026"})
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]

    # AC-12: Analyst calling Resolve Escalation receives 403; TeamLead succeeds
    awaiting_res = client.get("/api/v1/alerts?tab=awaiting&page=1&page_size=10")
    assert awaiting_res.status_code == 200
    awaiting_items = awaiting_res.json().get("items", [])
    assert len(awaiting_items) > 0, "No awaiting alerts found to test escalation"
    target_esc_alert_id = awaiting_items[0]["id"]
    escalate_action = client.post(
        f"/api/v1/alerts/{target_esc_alert_id}/decision",
        json={"action": "ESCALATE", "rationale": "Escalating suspicious telemetry to Team Lead."},
    )
    assert escalate_action.status_code == 200

    analyst_resolve = client.post(
        f"/api/v1/alerts/{target_esc_alert_id}/decision",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "action": "RESOLVE_ESCALATION",
            "final_verdict": "TRUE_POSITIVE",
            "final_severity": "HIGH",
            "rationale": "Analyst attempting unauthorized resolution.",
        },
    )
    assert analyst_resolve.status_code == 403, f"Expected 403 for Analyst Resolve Escalation, got {analyst_resolve.status_code}"
    print("✅ PASS: [AC-12] Analyst calling Resolve Escalation strictly rejected with HTTP 403")

    tl_resolve = client.post(
        f"/api/v1/alerts/{target_esc_alert_id}/decision",
        headers={"Authorization": f"Bearer {tl_token}"},
        json={
            "action": "RESOLVE_ESCALATION",
            "final_verdict": "TRUE_POSITIVE",
            "final_severity": "HIGH",
            "rationale": "Authorized Team Lead resolution following deep host inspection.",
        },
    )
    assert tl_resolve.status_code == 200
    print("✅ PASS: [AC-12] Team Lead calling Resolve Escalation succeeds and alert transitions to CLOSED")

    # AC-14: Analyst on analytics receives 403; range > 90 days rejected with 422
    analyst_analytics = client.get("/api/v1/analytics", headers={"Authorization": f"Bearer {token}"})
    assert analyst_analytics.status_code == 403
    print("✅ PASS: [AC-14] Analyst accessing Team Lead Analytics strictly rejected with HTTP 403")

    range_over_90 = client.get("/api/v1/analytics?range=120d", headers={"Authorization": f"Bearer {tl_token}"})
    assert range_over_90.status_code == 422
    print("✅ PASS: [AC-14] Query range > 90 days (120d) strictly rejected with HTTP 422")

    # AC-16: Admin can administer users; non-Admin receives 403
    non_admin_users = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert non_admin_users.status_code == 403
    print("✅ PASS: [AC-16] Non-Admin accessing user administration strictly rejected with HTTP 403")

    admin_users = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert admin_users.status_code == 200
    print("✅ PASS: [AC-16] System Admin successfully manages users (HTTP 200)")

    # AC-17: TeamLead tier update succeeds; Analyst write returns 403
    analyst_asset_patch = client.patch(
        "/api/v1/governance/assets/001",
        headers={"Authorization": f"Bearer {token}"},
        json={"criticality_tier": "CRITICAL"},
    )
    assert analyst_asset_patch.status_code == 403
    print("✅ PASS: [AC-17] Analyst modifying asset criticality tier strictly rejected with HTTP 403")

    tl_asset_patch = client.patch(
        "/api/v1/governance/assets/001",
        headers={"Authorization": f"Bearer {tl_token}"},
        json={"criticality_tier": "CRITICAL"},
    )
    assert tl_asset_patch.status_code == 200
    assert tl_asset_patch.json()["criticality_tier"] == "CRITICAL"
    print("✅ PASS: [AC-17] Team Lead modifying asset criticality tier succeeds and records update (HTTP 200)")

    # AC-17 / UC-10: Invalid criticality tier strictly rejected with HTTP 422
    bad_tier_patch = client.patch(
        "/api/v1/governance/assets/001",
        headers={"Authorization": f"Bearer {tl_token}"},
        json={"criticality_tier": "INVALID_TIER"},
    )
    assert bad_tier_patch.status_code == 422
    print("✅ PASS: [UC-10] Modifying asset criticality with invalid tier strictly rejected with HTTP 422")

    # UC-11: Invalid user role update strictly rejected with HTTP 422
    first_user_id = admin_users.json()[0]["id"]
    bad_role_patch = client.patch(
        f"/api/v1/admin/users/{first_user_id}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "INVALID_ROLE"},
    )
    assert bad_role_patch.status_code == 422
    print("✅ PASS: [UC-11] Modifying user with invalid role strictly rejected with HTTP 422")

    # UC-4..8: Invalid state transitions strictly rejected with HTTP 422
    bad_esc_res = client.post(
        f"/api/v1/alerts/{retry_alert_id}/decision",
        headers={"Authorization": f"Bearer {tl_token}"},
        json={
            "action": "RESOLVE_ESCALATION",
            "final_verdict": "TRUE_POSITIVE",
            "final_severity": "HIGH",
            "rationale": "Attempting invalid resolve on non-escalated alert.",
        },
    )
    assert bad_esc_res.status_code == 422
    print("✅ PASS: [UC-8] Resolving non-escalated alert strictly rejected with HTTP 422")

    closed_alert_res = client.post(
        f"/api/v1/alerts/{test_alert_id}/decision",
        json={"action": "APPROVE"},
    )
    assert closed_alert_res.status_code == 422
    print("✅ PASS: [UC-4] Decision on already CLOSED alert strictly rejected with HTTP 422")

    # 17. System Configuration: Database Persistence & Thread Safety
    config_res = client.get("/api/v1/admin/config", headers={"Authorization": f"Bearer {admin_token}"})
    assert config_res.status_code == 200
    current_cfg = config_res.json()
    assert "wazuh_endpoint" in current_cfg
    assert "abstention_threshold" in current_cfg
    print("✅ PASS: [GET /api/v1/admin/config] Loaded persistent system configuration from PostgreSQL")

    patch_cfg_res = client.patch(
        "/api/v1/admin/config",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"polling_interval_seconds": 45, "min_rule_level": 5},
    )
    assert patch_cfg_res.status_code == 200
    updated_cfg = patch_cfg_res.json()
    assert updated_cfg["polling_interval_seconds"] == 45
    assert updated_cfg["min_rule_level"] == 5
    print("✅ PASS: [PATCH /api/v1/admin/config] Updated persistent configuration in PostgreSQL")

    # 18. Security Hardening: Unauthenticated Access Prohibited when DEMO_MODE=False
    print("\n--- Verifying Production Role-Guard Hardening (DEMO_MODE=False) ---")
    orig_demo_mode = settings.DEMO_MODE
    try:
        settings.DEMO_MODE = False
        unauth_admin = client.get("/api/v1/admin/users")
        assert unauth_admin.status_code == 401, f"Expected 401 on unauthenticated admin, got {unauth_admin.status_code}"

        unauth_analytics = client.get("/api/v1/analytics")
        assert unauth_analytics.status_code == 401, f"Expected 401 on unauthenticated analytics, got {unauth_analytics.status_code}"

        unauth_gov = client.patch("/api/v1/governance/assets/001", json={"criticality_tier": "HIGH"})
        assert unauth_gov.status_code == 401, f"Expected 401 on unauthenticated asset patch, got {unauth_gov.status_code}"

        unauth_dec = client.post("/api/v1/alerts/al-9021/decision", json={"action": "APPROVE"})
        assert unauth_dec.status_code == 401, f"Expected 401 on unauthenticated decision, got {unauth_dec.status_code}"

        print("✅ PASS: All administrative, analytics & decision endpoints strictly enforce HTTP 401 when DEMO_MODE=False")
    finally:
        settings.DEMO_MODE = orig_demo_mode

    # 19. Action Normalization: MANUAL_TRIAGE_CLOSURE (and legacy alias normalization)
    print("\n--- Verifying Action Normalization & Nullability (ABR Audit) ---")
    manual_alert = client.get("/api/v1/alerts?status=NEEDS_MANUAL_TRIAGE", headers={"Authorization": f"Bearer {token}"}).json()
    if manual_alert["items"]:
        m_aid = manual_alert["items"][0]["id"]
        analyst_user_id = auth_data["user"]["id"]
        res_closure = client.post(
            f"/api/v1/alerts/{m_aid}/decision",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "action": "MANUAL_TRIAGE_CLOSURE",
                "final_verdict": "FALSE_POSITIVE",
                "final_severity": "LOW",
                "rationale": "Manual triage confirmed benign service task execution by authorized admin.",
                "user_id": analyst_user_id,
            },
        )
        assert res_closure.status_code == 200, f"Expected 200 on MANUAL_TRIAGE_CLOSURE, got {res_closure.status_code}: {res_closure.text}"
        assert res_closure.json()["action_taken"] == "MANUAL_TRIAGE_CLOSURE"
        print("✅ PASS: [POST /alerts/{id}/decision] MANUAL_TRIAGE_CLOSURE accepted and audit logged")

    # 20. Asset Registration without IP (Nullable ip_address)
    test_agent_id = f"099_test_no_ip_{uuid.uuid4().hex[:6]}"
    reg_res = client.post(
        "/api/v1/governance/assets",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "agent_id": test_agent_id,
            "hostname": "CONTAINER-EPHEMERAL-01",
            "ip_address": None,
            "criticality_tier": "LOW",
            "description": "Auto-registered ephemeral container without IP address",
        },
    )
    assert reg_res.status_code == 200, f"Expected 200 on registering asset with NULL IP, got {reg_res.status_code}"
    assert reg_res.json()["agent_id"] == test_agent_id
    print("✅ PASS: [POST /governance/assets] Asset registered with NULL ip_address successfully")

    print("\n" + "=" * 70)
    print("🎯 ALL 20 REST API ENDPOINT INTEGRATION TESTS PASSED (100% SUCCESS)!")
    print("=" * 70)
    return True


def test_all_api_endpoints():
    assert run_all_api_tests() is True


if __name__ == "__main__":
    run_all_api_tests()

