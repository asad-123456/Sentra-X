from fastapi.testclient import TestClient

from app.main import app
from app.settings import get_settings


def test_health_returns_ok():
    r = TestClient(app).get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_settings_defaults():
    s = get_settings()
    assert s.wazuh_min_level == 4
    assert s.wazuh_poll_interval_seconds == 30