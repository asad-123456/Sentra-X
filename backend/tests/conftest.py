"""Test configuration. app.config reads settings when the app is first imported, so this runs first.

The default is DEMO_MODE=false (production-safe). Asad's endpoint suite (test_api_endpoints.py) deliberately
exercises the demo-open routes without a token, so it needs DEMO_MODE=true. Tests that check real authentication
(test_auth_hardening.py, test_assets.py) switch DEMO_MODE off themselves with monkeypatch."""
import os

os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("TRIAGE_ENABLED", "false")   # tests start the dispatcher themselves when they need it
