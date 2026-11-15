"""AC-17 / FR-9 against the real asset routes in app/routers/governance.py, run on sentrax_test.
DEMO_MODE is forced off, so the role rules are the real ones.

Tests marked xfail document gaps in the existing routes (proposed to Asad). When a gap is fixed its
test starts to pass; then delete the xfail marker."""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.assets.service import get_asset_tier
from app.auth import hash_password
from app.config import settings
from app.database import get_db
from app.main import app
from app.models import Asset, User
from app.models.base import Base

TABLES = [Base.metadata.tables[n] for n in ("users", "assets")]
PW = "Passw0rd!x"
OLD = datetime(2026, 1, 1, tzinfo=timezone.utc)
URL = "/api/v1/governance/assets"


@pytest.fixture(scope="module")
def factory():
    url = make_url(settings.DATABASE_URL).set(database="sentrax_test")
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"sentrax_test database not reachable: {exc}")
    Base.metadata.drop_all(engine, tables=TABLES)
    Base.metadata.create_all(engine, tables=TABLES)
    yield sessionmaker(engine, expire_on_commit=False)
    Base.metadata.drop_all(engine, tables=TABLES)
    engine.dispose()


@pytest.fixture(autouse=True)
def clean(factory, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)  # real auth rules, no open demo access
    with factory.begin() as s:
        s.execute(text("TRUNCATE users, assets CASCADE"))
        s.add_all([
            Asset(agent_id="001", hostname="ubuntu-1", ip_address="10.0.0.11",
                  criticality_tier="MEDIUM", updated_at=OLD),
            Asset(agent_id="002", hostname="ubuntu-2", ip_address="10.0.0.12",
                  criticality_tier="LOW", updated_at=OLD),
        ])


@pytest.fixture
def client(factory):
    def override():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def make_user(factory, username, role, active=True):
    user = User(id=uuid.uuid4(), username=username, email=f"{username}@sentrax.dev",
                password_hash=hash_password(PW), role=role, is_active=active)
    with factory.begin() as s:
        s.add(user)
    return user


def headers(client, username):
    r = client.post("/api/v1/auth/login", json={"username": username, "password": PW})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def row(factory, agent_id="001"):
    with factory() as s:
        return s.execute(text("SELECT criticality_tier, updated_by, updated_at FROM assets WHERE agent_id=:a"),
                         {"a": agent_id}).one()


# ---- the worker hook ----
def test_get_asset_tier_reads_current_value_and_defaults_to_medium(factory):
    with factory() as s:
        assert get_asset_tier(s, "001") == "MEDIUM"
        assert get_asset_tier(s, "002") == "LOW"
        assert get_asset_tier(s, "does-not-exist") == "MEDIUM"


# ---- AC-17 ----
def test_ac17_teamlead_update_is_recorded_and_seen_by_next_lookup(client, factory):
    lead = make_user(factory, "lead", "TeamLead")
    r = client.patch(f"{URL}/001", headers=headers(client, "lead"), json={"criticality_tier": "CRITICAL"})
    assert r.status_code == 200 and r.json()["criticality_tier"] == "CRITICAL"
    tier, updated_by, updated_at = row(factory)
    assert tier == "CRITICAL" and updated_by == lead.id and updated_at > OLD
    with factory() as s:  # what the worker reads for its next evidence pack
        assert get_asset_tier(s, "001") == "CRITICAL"


def test_admin_can_update(client, factory):
    make_user(factory, "boss", "Admin")
    r = client.patch(f"{URL}/002", headers=headers(client, "boss"), json={"criticality_tier": "HIGH"})
    assert r.status_code == 200 and row(factory, "002").criticality_tier == "HIGH"


def test_analyst_gets_403_and_nothing_changes(client, factory):
    make_user(factory, "ann", "Analyst")
    r = client.patch(f"{URL}/001", headers=headers(client, "ann"), json={"criticality_tier": "HIGH"})
    assert r.status_code == 403
    assert row(factory).criticality_tier == "MEDIUM"


def test_no_token_gets_401_on_update(client, factory):
    r = client.patch(f"{URL}/001", json={"criticality_tier": "HIGH"})
    assert r.status_code == 401 and row(factory).criticality_tier == "MEDIUM"


@pytest.mark.parametrize("payload", [{"criticality_tier": "URGENT"}, {"criticality_tier": "high"}, {}])
def test_invalid_tier_is_422_and_changes_nothing(client, factory, payload):
    make_user(factory, "lead", "TeamLead")
    r = client.patch(f"{URL}/001", headers=headers(client, "lead"), json=payload)
    assert r.status_code == 422 and row(factory).criticality_tier == "MEDIUM"


def test_unknown_agent_is_404(client, factory):
    make_user(factory, "lead", "TeamLead")
    r = client.patch(f"{URL}/999", headers=headers(client, "lead"), json={"criticality_tier": "HIGH"})
    assert r.status_code == 404


# ---- known gaps in the existing routes (proposed to Asad) ----
@pytest.mark.xfail(reason="GET /governance/assets has no authentication at all", strict=False)
def test_gap_listing_requires_login(client):
    assert client.get(URL).status_code == 401


@pytest.mark.xfail(reason="updated_by is taken from the request body, so an editor can name someone else", strict=False)
def test_gap_updated_by_cannot_be_spoofed(client, factory):
    lead = make_user(factory, "lead", "TeamLead")
    boss = make_user(factory, "boss", "Admin")
    client.patch(f"{URL}/001", headers=headers(client, "lead"),
                 json={"criticality_tier": "HIGH", "updated_by": str(boss.id)})
    assert row(factory).updated_by == lead.id


@pytest.mark.xfail(reason="a deactivated user's token still works on this route", strict=False)
def test_gap_deactivated_user_cannot_update(client, factory):
    make_user(factory, "lead", "TeamLead")
    h = headers(client, "lead")
    with factory.begin() as s:
        s.execute(text("UPDATE users SET is_active = false WHERE username = 'lead'"))
    r = client.patch(f"{URL}/001", headers=h, json={"criticality_tier": "HIGH"})
    assert r.status_code in (401, 403) and row(factory).criticality_tier == "MEDIUM"
