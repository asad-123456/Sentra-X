import pytest

from app.services.llm_adapter import clear_adapter_cache, get_adapter


@pytest.fixture(autouse=True)
def _fresh_cache():
    clear_adapter_cache()
    yield
    clear_adapter_cache()


def test_real_adapter_is_cached_per_key_and_model(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "key-a")
    first = get_adapter("gemini")
    assert get_adapter("gemini") is first
    monkeypatch.setenv("GEMINI_API_KEY", "key-b")
    assert get_adapter("gemini") is not first


def test_mock_is_never_cached():
    assert get_adapter("mock") is not get_adapter("mock")

def test_explicit_model_overrides_env_and_gets_its_own_cache_entry(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key-a")
    a = get_adapter("gemini", "model-x")
    assert a.model_name == "model-x"
    assert get_adapter("gemini", "model-x") is a
    assert get_adapter("gemini", "model-y") is not a