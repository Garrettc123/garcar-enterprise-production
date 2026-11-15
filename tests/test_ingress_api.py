import asyncio
import hashlib
import hmac
import time
from contextlib import asynccontextmanager

import src.main as main
from fastapi import HTTPException
import pytest
from fastapi.testclient import TestClient


SECRET = "integration-test-secret-with-more-than-32-bytes"


def signed_headers(body: bytes, timestamp: int) -> dict[str, str]:
    message = str(timestamp).encode("ascii") + b"." + body
    digest = hmac.new(SECRET.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return {
        "x-garcar-timestamp": str(timestamp),
        "x-garcar-signature": "sha256=" + digest,
        "content-type": "application/json",
    }


def test_permit_endpoint_rejects_unsigned_request_before_ledger_write(monkeypatch):
    @asynccontextmanager
    async def no_lifespan(app):
        yield

    monkeypatch.setattr(main.app.router, "lifespan_context", no_lifespan)
    monkeypatch.setattr(main, "vault_data", {"PERMIT_INGEST_HMAC_SECRET": SECRET})
    monkeypatch.setattr(
        main,
        "seal_record",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("unauthenticated request reached the ledger")
        ),
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/webhook/permits/dfw",
            json={
                "permit_id": "P-1",
                "municipality": "DFW",
                "contractor_name": "Example Co",
                "property_address": "1 Main St",
                "valuation": 1000,
                "filing_date": "2026-10-30",
            },
        )
    assert response.status_code == 401


def test_permit_endpoint_accepts_valid_signed_request(monkeypatch):
    @asynccontextmanager
    async def no_lifespan(app):
        yield

    monkeypatch.setattr(main.app.router, "lifespan_context", no_lifespan)
    monkeypatch.setattr(main, "vault_data", {"PERMIT_INGEST_HMAC_SECRET": SECRET})
    writes = []
    monkeypatch.setattr(
        main,
        "seal_record",
        lambda record, bucket, region, retention: writes.append(record)
        or {"result": "sealed", "sha256": "abc", "key": "records/ab/abc.json"},
    )
    body = (
        b'{"permit_id":"P-1","municipality":"DFW","contractor_name":"Example Co",'
        b'"property_address":"1 Main St","valuation":1000,"filing_date":"2026-10-30"}'
    )
    timestamp = int(time.time())
    with TestClient(main.app) as client:
        response = client.post(
            "/webhook/permits/dfw",
            content=body,
            headers=signed_headers(body, timestamp),
        )
    assert response.status_code == 200
    assert len(writes) == 1
    assert response.json()["decision"]["decision"] == "REVIEW_REQUIRED"


def test_permit_endpoint_rejects_oversized_payload(monkeypatch):
    @asynccontextmanager
    async def no_lifespan(app):
        yield

    monkeypatch.setattr(main.app.router, "lifespan_context", no_lifespan)
    monkeypatch.setattr(main, "vault_data", {"PERMIT_INGEST_HMAC_SECRET": SECRET})
    monkeypatch.setattr(
        main,
        "seal_record",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("oversized request reached the ledger")
        ),
    )
    with TestClient(main.app) as client:
        response = client.post(
            "/webhook/permits/dfw",
            content=b"x" * (1_048_577),
        )
    assert response.status_code == 413



def test_streaming_body_reader_stops_when_limit_is_exceeded():
    class ChunkedRequest:
        headers = {}

        async def stream(self):
            yield b"x" * 700_000
            yield b"y" * 400_000

    with pytest.raises(HTTPException) as error:
        asyncio.run(main.read_limited_body(ChunkedRequest(), limit=1_048_576))
    assert error.value.status_code == 413
