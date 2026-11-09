from contextlib import contextmanager
import asyncio

import pytest
from fastapi import HTTPException

from src import main


def test_health_reports_database_ready_when_migration_exists(monkeypatch):
    class Result:
        def fetchone(self):
            return (1,)

    class Connection:
        def execute(self, *_args, **_kwargs):
            return Result()

    @contextmanager
    def fake_connection():
        yield Connection()

    monkeypatch.setenv("ENABLE_GOVERNANCE_DB", "true")
    monkeypatch.setattr(main, "db_connection", fake_connection)
    result = asyncio.run(main.health())
    assert result["status"] == "ok"
    assert result["governance_database"] == "connected"


def test_health_fails_when_migration_is_missing(monkeypatch):
    class Result:
        def fetchone(self):
            return None

    class Connection:
        def execute(self, *_args, **_kwargs):
            return Result()

    @contextmanager
    def fake_connection():
        yield Connection()

    monkeypatch.setenv("ENABLE_GOVERNANCE_DB", "true")
    monkeypatch.setattr(main, "db_connection", fake_connection)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.health())
    assert exc.value.status_code == 503
