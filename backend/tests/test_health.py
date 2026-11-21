from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app import main
from app.ingestion.wazuh_settings import get_wazuh_settings
from app.main import app


@pytest.mark.parametrize("path", ["/api/ready", "/api/health"])
def test_readiness_endpoint_responds(monkeypatch, path):
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    monkeypatch.setattr(main, "sync_engine", engine)
    r = TestClient(app).get(path)
    assert r.status_code == 200
    assert r.json() == {"status": "HEALTHY", "database": "CONNECTED", "engine": "PostgreSQL"}
    assert str(connection.execute.call_args.args[0]) == "SELECT 1"


@pytest.mark.parametrize("path", ["/api/ready", "/api/health"])
def test_db_failure_is_unready_without_exposing_connection_details(monkeypatch, path):
    engine = MagicMock()
    engine.connect.side_effect = OperationalError(None, None, ValueError("private connection detail"))
    monkeypatch.setattr(main, "sync_engine", engine)

    client = TestClient(app)
    liveness = client.get("/api/live")
    assert liveness.status_code == 200
    assert liveness.json() == {"status": "ALIVE"}
    engine.connect.assert_not_called()

    readiness = client.get(path)
    assert readiness.status_code == 503
    assert readiness.json() == {"status": "DEGRADED", "database": "DISCONNECTED", "engine": "PostgreSQL"}


def test_wazuh_settings_defaults():
    w = get_wazuh_settings()
    assert w.WAZUH_MIN_LEVEL == 4
    assert w.WAZUH_POLL_INTERVAL_SECONDS == 30


def test_api_lifespan_starts_and_stops_triage_worker(monkeypatch):
    events = []
    monkeypatch.setattr(get_wazuh_settings(), "WAZUH_INGEST_MODE", "replay")
    monkeypatch.setattr(main, "start_worker", lambda: events.append("start"))
    monkeypatch.setattr(main, "stop_worker", lambda: events.append("stop"))

    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert events == ["start"]

    assert events == ["start", "stop"]
