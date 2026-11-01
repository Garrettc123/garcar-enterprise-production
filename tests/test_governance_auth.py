import hashlib

import pytest
from fastapi import HTTPException

from src.governance.router import (
    _configured_agent_keys,
    _require_owned_namespace,
    configure_runtime_secrets,
    require_agent,
)


@pytest.fixture(autouse=True)
def clear_runtime_secrets():
    configure_runtime_secrets({})
    yield
    configure_runtime_secrets({})


def test_named_agent_key_resolves_to_configured_identity():
    key = "a" * 40
    configure_runtime_secrets({"GARCAR_AGENT_API_KEYS": f"sales-agent:{key}"})
    assert _configured_agent_keys() == [("sales-agent", key)]
    assert require_agent(key) == "sales-agent"


def test_legacy_agent_key_gets_stable_non_secret_identity():
    key = "b" * 40
    expected = "agent_" + hashlib.sha256(key.encode()).hexdigest()[:16]
    configure_runtime_secrets({"GARCAR_AGENT_API_KEYS": key})
    assert require_agent(key) == expected


def test_invalid_or_short_agent_key_is_rejected():
    configure_runtime_secrets({"GARCAR_AGENT_API_KEYS": "short"})
    with pytest.raises(HTTPException) as exc:
        require_agent("short")
    assert exc.value.status_code == 401


def test_agent_cannot_access_another_agents_memory_namespace():
    with pytest.raises(HTTPException) as exc:
        _require_owned_namespace("finance-agent", "sales-agent")
    assert exc.value.status_code == 403


def test_agent_can_access_its_own_memory_namespace():
    _require_owned_namespace("sales-agent", "sales-agent")


def test_missing_kill_switch_state_fails_closed(monkeypatch):
    from contextlib import contextmanager
    from src.governance import router as governance

    class FakeResult:
        def fetchone(self):
            return None

    class FakeConnection:
        def execute(self, *_args, **_kwargs):
            return FakeResult()

    @contextmanager
    def fake_connection():
        yield FakeConnection()

    monkeypatch.setattr(governance, "db_connection", fake_connection)
    assert governance.execution_is_blocked() is True


def test_enabled_kill_switch_blocks_execution(monkeypatch):
    from contextlib import contextmanager
    from src.governance import router as governance

    class FakeResult:
        def fetchone(self):
            return {"enabled": True}

    class FakeConnection:
        def execute(self, *_args, **_kwargs):
            return FakeResult()

    @contextmanager
    def fake_connection():
        yield FakeConnection()

    monkeypatch.setattr(governance, "db_connection", fake_connection)
    assert governance.execution_is_blocked() is True


def test_database_connection_errors_are_reported_as_unavailable(monkeypatch):
    import psycopg
    from fastapi import HTTPException
    from src.governance import router as governance

    monkeypatch.setenv("DATABASE_URL", "postgresql://invalid:invalid@127.0.0.1:1/invalid")

    def fail_connect(*_args, **_kwargs):
        raise psycopg.OperationalError("simulated database outage")

    monkeypatch.setattr(governance.psycopg, "connect", fail_connect)
    with pytest.raises(HTTPException) as exc:
        with governance.db_connection():
            pass
    assert exc.value.status_code == 503
    assert exc.value.detail == "Governance database unavailable"


def test_disabled_kill_switch_allows_preflight(monkeypatch):
    from contextlib import contextmanager
    from src.governance import router as governance

    class FakeResult:
        def fetchone(self):
            return {"enabled": False}

    class FakeConnection:
        def execute(self, *_args, **_kwargs):
            return FakeResult()

    @contextmanager
    def fake_connection():
        yield FakeConnection()

    monkeypatch.setattr(governance, "db_connection", fake_connection)
    assert governance.execution_is_blocked() is False
