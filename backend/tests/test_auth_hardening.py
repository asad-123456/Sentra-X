"""AC-15 and AC-16 (FR-8) against Asad's real auth and admin routes, run on sentrax_test with DEMO_MODE off."""
import logging
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.auth import create_access_token, hash_password, require_roles
from app.config import settings
from app.database import get_db
from app.main import app
from app.models import User
from app.models.base import Base
from app.routers.auth import FAILED_LOGIN_ATTEMPTS

TABLES = [Base.metadata.tables["users"]]
PW = "Passw0rd!x"
ADMIN_USERS = "/api/v1/admin/users"


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
    monkeypatch.setattr(settings, "DEMO_MODE", False)            # real authentication rules
    monkeypatch.setattr(settings, "DEFAULT_NEW_USER_PASSWORD", "")
    FAILED_LOGIN_ATTEMPTS.clear()                                 # the login rate limit is per IP and global
    with factory.begin() as s:
        s.execute(text("TRUNCATE users CASCADE"))


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


def login(client, ident, password=PW):
    return client.post("/api/v1/auth/login", json={"username": ident, "password": password})


def headers(client, username):
    r = login(client, username)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---- AC-15: authentication ----
def test_wrong_password_and_unknown_user_are_401_without_token(client, factory):
    make_user(factory, "alice", "Analyst")
    bad = login(client, "alice", "WrongPass123")
    assert bad.status_code == 401 and "access_token" not in bad.json()
    assert login(client, "nobody").status_code == 401


def test_login_by_username_or_email_returns_a_token_for_that_user(client, factory):
    user = make_user(factory, "alice", "Analyst")
    for ident in ("alice", "alice@sentrax.dev", "ALICE@sentrax.dev"):
        r = login(client, ident)
        assert r.status_code == 200, ident
    claims = jwt.decode(r.json()["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert claims["sub"] == str(user.id) and "exp" in claims


def test_no_expired_garbage_or_forged_token_is_401(client, factory):
    user = make_user(factory, "boss", "Admin")
    expired = create_access_token({"sub": str(user.id), "role": "Admin"}, timedelta(minutes=-5))
    forged = jwt.encode({"sub": str(user.id), "role": "Admin", "exp": 4102444800}, "some-other-secret", algorithm="HS256")
    no_exp = jwt.encode({"sub": str(user.id), "role": "Admin"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    assert client.get(ADMIN_USERS).status_code == 401
    for token in (expired, forged, no_exp, "garbage"):
        assert client.get(ADMIN_USERS, headers={"Authorization": f"Bearer {token}"}).status_code == 401, token[:12]


# ---- AC-16: roles ----
@pytest.mark.parametrize("role", ["Analyst", "TeamLead"])
def test_non_admin_gets_403_on_user_administration(client, factory, role):
    make_user(factory, "u1", role)
    assert client.get(ADMIN_USERS, headers=headers(client, "u1")).status_code == 403


def test_admin_can_list_users(client, factory):
    make_user(factory, "boss", "Admin")
    r = client.get(ADMIN_USERS, headers=headers(client, "boss"))
    assert r.status_code == 200 and [u["username"] for u in r.json()] == ["boss"]


def test_demo_mode_is_the_only_way_to_call_admin_routes_without_a_token(client, factory, monkeypatch):
    make_user(factory, "boss", "Admin")
    assert client.get(ADMIN_USERS).status_code == 401           # DEMO_MODE off
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    assert client.get(ADMIN_USERS).status_code == 200           # demo only


# ---- role and is_active come from the database on every request ----
def test_deactivated_user_loses_access_immediately(client, factory):
    make_user(factory, "boss", "Admin")
    bob = make_user(factory, "bob", "Analyst")
    bob_headers = headers(client, "bob")
    assert client.get("/api/v1/auth/me", headers=bob_headers).status_code == 200
    r = client.patch(f"{ADMIN_USERS}/{bob.id}/status", headers=headers(client, "boss"), json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert client.get("/api/v1/auth/me", headers=bob_headers).status_code in (401, 403)
    assert login(client, "bob").status_code in (401, 403)


def test_demoted_admin_old_token_stops_working(client, factory):
    make_user(factory, "boss", "Admin")
    carol = make_user(factory, "carol", "Admin")
    old = headers(client, "carol")
    assert client.get(ADMIN_USERS, headers=old).status_code == 200
    r = client.patch(f"{ADMIN_USERS}/{carol.id}/role", headers=headers(client, "boss"), json={"role": "Analyst"})
    assert r.status_code == 200
    assert client.get(ADMIN_USERS, headers=old).status_code == 403   # the role in the token was Admin; the DB says Analyst


def test_admin_cannot_lock_themselves_out(client, factory):
    boss = make_user(factory, "boss", "Admin")
    h = headers(client, "boss")
    assert client.patch(f"{ADMIN_USERS}/{boss.id}/status", headers=h, json={"is_active": False}).status_code == 400
    assert client.patch(f"{ADMIN_USERS}/{boss.id}/role", headers=h, json={"role": "Analyst"}).status_code == 400
    assert client.patch(f"{ADMIN_USERS}/{boss.id}/role", headers=h, json={"role": "BOSS"}).status_code == 422
    assert client.patch(f"{ADMIN_USERS}/{boss.id}/role", headers=h, json={"role": "Admin"}).status_code == 200


# ---- creating users ----
def test_create_user_with_password_then_login(client, factory):
    make_user(factory, "boss", "Admin")
    h = headers(client, "boss")
    r = client.post(ADMIN_USERS, headers=h, json={"username": "newbie", "email": "newbie@sentrax.dev",
                                                  "password": "Newbie123!", "role": "Analyst"})
    assert r.status_code == 200 and "temporary_password" not in r.json() and "password_hash" not in r.json()
    assert login(client, "newbie", "Newbie123!").status_code == 200


def test_create_user_without_password_generates_a_temporary_one(client, factory):
    make_user(factory, "boss", "Admin")
    r = client.post(ADMIN_USERS, headers=headers(client, "boss"),
                    json={"username": "newbie", "email": "newbie@sentrax.dev", "role": "Analyst"})
    assert r.status_code == 200
    temp = r.json()["temporary_password"]
    assert len(temp) >= 12 and temp != "sentrax2026"
    assert login(client, "newbie", temp).status_code == 200


def test_create_user_without_password_uses_the_configured_default(client, factory, monkeypatch):
    monkeypatch.setattr(settings, "DEFAULT_NEW_USER_PASSWORD", "demo-Default-1")
    make_user(factory, "boss", "Admin")
    r = client.post(ADMIN_USERS, headers=headers(client, "boss"),
                    json={"username": "newbie", "email": "newbie@sentrax.dev", "role": "Analyst"})
    assert r.status_code == 200 and "temporary_password" not in r.json()
    assert login(client, "newbie", "demo-Default-1").status_code == 200


def test_create_user_validation_and_duplicates(client, factory):
    make_user(factory, "boss", "Admin")
    h = headers(client, "boss")
    ok = {"username": "dave", "email": "dave@sentrax.dev", "password": "Dave12345!", "role": "Analyst"}
    assert client.post(ADMIN_USERS, headers=h, json=ok).status_code == 200
    assert client.post(ADMIN_USERS, headers=h, json=ok).status_code == 409
    assert client.post(ADMIN_USERS, headers=h, json={**ok, "username": "d2", "email": "d2@sentrax.dev"}).status_code == 422   # username too short
    assert client.post(ADMIN_USERS, headers=h, json={**ok, "username": "dave2", "email": "not-an-email"}).status_code == 422
    assert client.post(ADMIN_USERS, headers=h, json={**ok, "username": "dave3", "email": "d3@sentrax.dev", "password": "short"}).status_code == 422
    assert client.post(ADMIN_USERS, headers=h, json={**ok, "username": "dave4", "email": "d4@sentrax.dev", "role": "Boss"}).status_code == 422
    assert client.post(ADMIN_USERS, headers=h, json={**ok, "username": "dave5", "email": "d5@sentrax.dev", "password": "a" * 73}).status_code == 422


# ---- security log ----
def test_failed_login_is_logged_without_the_password(client, factory, caplog):
    make_user(factory, "alice", "Analyst")
    caplog.set_level(logging.INFO, logger="sentrax.security")
    login(client, "alice", "WrongPass123")
    assert "login_failed" in caplog.text and "reason=bad_password" in caplog.text
    assert "WrongPass123" not in caplog.text


def test_admin_actions_are_logged(client, factory, caplog):
    make_user(factory, "boss", "Admin")
    bob = make_user(factory, "bob", "Analyst")
    h = headers(client, "boss")
    caplog.set_level(logging.INFO, logger="sentrax.security")
    client.patch(f"{ADMIN_USERS}/{bob.id}/status", headers=h, json={"is_active": False})
    assert "user_status_changed" in caplog.text and "by=boss" in caplog.text and "target=bob" in caplog.text


def test_require_roles_rejects_unknown_roles():
    with pytest.raises(ValueError):
        require_roles("Boss")
