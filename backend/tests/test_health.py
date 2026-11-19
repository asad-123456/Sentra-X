from fastapi.testclient import TestClient

from app import main
from app.ingestion.wazuh_settings import get_wazuh_settings
from app.main import app


def test_health_endpoint_responds():
    r = TestClient(app).get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] in ("HEALTHY", "DEGRADED")


def test_wazuh_settings_defaults():
    w = get_wazuh_settings()
    assert w.WAZUH_MIN_LEVEL == 4
    assert w.WAZUH_POLL_INTERVAL_SECONDS == 30


def test_api_lifespan_starts_and_stops_triage_worker(monkeypatch):
    events = []
    monkeypatch.setattr(main, "start_worker", lambda: events.append("start"))
    monkeypatch.setattr(main, "stop_worker", lambda: events.append("stop"))

    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert events == ["start"]

    assert events == ["start", "stop"]
