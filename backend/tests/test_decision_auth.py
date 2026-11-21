from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.config import settings
from app.database import get_db
from app.main import app
from app.models import Alert, AnalystDecisionAudit, Asset, FeedbackExemplar, User


@pytest.mark.parametrize(
    ("actor_role", "session_state", "action", "expected"),
    [
        ("Analyst", "missing", "OVERRIDE", 401),
        ("Analyst", "demo_missing", "OVERRIDE", 401),
        ("Analyst", "expired", "OVERRIDE", 401),
        ("Analyst", "disabled", "OVERRIDE", 403),
        ("Analyst", "active", "RESOLVE_ESCALATION", 403),
        ("Analyst", "active", "OVERRIDE", 200),
        ("TeamLead", "active", "RESOLVE_ESCALATION", 200),
        ("Admin", "active", "RESOLVE_ESCALATION", 200),
    ],
)
def test_decisions_use_the_active_account(contributor_test_engine, monkeypatch, actor_role, session_state, action, expected):
    monkeypatch.setattr(settings, "DEMO_MODE", session_state == "demo_missing")
    with contributor_test_engine.connect() as connection:
        connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
            tag = uuid4().hex[:10]
            actor = User(username=f"actor-{tag}", email=f"actor-{tag}@example.test", password_hash="unused", role=actor_role)
            other = User(username=f"other-{tag}", email=f"other-{tag}@example.test", password_hash="unused", role="Admin")
            db.add_all([actor, other, Asset(agent_id=tag, hostname="test-host")])
            db.flush()
            initial_status = "ESCALATED" if action == "RESOLVE_ESCALATION" else "AWAITING_ANALYST"
            alert = Alert(
                wazuh_alert_id=tag,
                rule_id="5710",
                rule_level=5,
                rule_description="Synthetic test",
                agent_id=tag,
                status=initial_status,
            )
            db.add(alert)
            db.flush()

            headers = {}
            if session_state not in ("missing", "demo_missing"):
                expires = timedelta(minutes=-5) if session_state == "expired" else None
                token = create_access_token({"sub": str(actor.id), "role": actor.role}, expires)
                headers["Authorization"] = f"Bearer {token}"
            if session_state == "disabled":
                actor.is_active = False
                db.flush()

            monkeypatch.setitem(app.dependency_overrides, get_db, lambda: db)
            client = TestClient(app)
            if session_state == "active":
                detail = client.get(f"/api/v1/alerts/{alert.id}", headers=headers)
                assert detail.status_code == 200
                if initial_status == "ESCALATED":
                    expected_actions = ["RESOLVE_ESCALATION"] if expected == 200 else []
                else:
                    expected_actions = ["OVERRIDE", "ESCALATE", "RETRY_AI"]
                assert detail.json()["available_actions"] == expected_actions

            response = client.post(f"/api/v1/alerts/{alert.id}/decision", headers=headers, json={
                "action": action,
                "user_id": str(other.id),
                "rationale": "Verified the synthetic test evidence.",
                "final_verdict": "FALSE_POSITIVE",
                "final_severity": "LOW",
                "save_as_exemplar": True,
            })
            assert response.status_code == expected, response.text
            audits = db.scalars(select(AnalystDecisionAudit).where(AnalystDecisionAudit.alert_id == alert.id)).all()
            exemplars = db.scalars(select(FeedbackExemplar).where(FeedbackExemplar.source_alert_id == alert.id)).all()
            if expected == 200:
                assert alert.status == "CLOSED"
                assert response.json()["user_id"] == str(actor.id)
                assert [audit.user_id for audit in audits] == [actor.id]
                assert [(example.user_id, example.created_by) for example in exemplars] == [(actor.id, actor.id)]
                assert client.get(f"/api/v1/alerts/{alert.id}", headers=headers).json()["available_actions"] == []
            else:
                assert alert.status == initial_status
                assert not audits and not exemplars
