"""Hardening audit (Oct 2026): webhook and money endpoints must fail closed.

- backend/payments.py Stripe webhook: 503 when STRIPE_WEBHOOK_SECRET is unset/empty,
  400 on a bad or missing signature, 200 only on a correctly signed event.
- billing/main.py /create-invoice and /transactions need BILLING_API_KEY.
- billing/revenue_allocator.py /allocate/execute needs ALLOCATOR_API_KEY.
No network calls: Stripe is never reached in these tests.
"""
import hashlib
import hmac
import importlib
import json
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

DUMMY = "unit-test-dummy-" + "k" * 24  # not a real secret


# ---------- Stripe webhook (backend/payments.py) ----------

@pytest.fixture
def webhook_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    import stripe as stripe_lib
    import payments
    from database import get_db

    monkeypatch.setattr(payments, "stripe", stripe_lib)
    app = FastAPI()
    app.include_router(payments.webhook_router)

    class _NoDB:
        def query(self, *a, **k):  # pragma: no cover - not reached for unknown event types
            raise AssertionError("db should not be touched")

    app.dependency_overrides[get_db] = lambda: _NoDB()
    return TestClient(app)


def _sign(payload: bytes, secret: str) -> str:
    ts = str(int(time.time()))
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"


EVENT = json.dumps({"id": "evt_test", "object": "event", "type": "ping.test",
                    "data": {"object": {}}}).encode()


@pytest.mark.parametrize("value", [None, "", "   "])
def test_webhook_503_when_secret_missing(webhook_client, monkeypatch, value):
    if value is None:
        monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    else:
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", value)
    r = webhook_client.post("/api/webhooks/stripe", content=EVENT,
                            headers={"stripe-signature": "t=1,v1=deadbeef"})
    assert r.status_code == 503


def test_webhook_unsigned_body_rejected_when_secret_missing(webhook_client, monkeypatch):
    """The old code parsed and trusted an unsigned body here. Now it must not."""
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    r = webhook_client.post("/api/webhooks/stripe", content=EVENT)
    assert r.status_code == 503


def test_webhook_400_on_missing_signature(webhook_client, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", DUMMY)
    r = webhook_client.post("/api/webhooks/stripe", content=EVENT)
    assert r.status_code == 400


def test_webhook_400_on_bad_signature(webhook_client, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", DUMMY)
    r = webhook_client.post("/api/webhooks/stripe", content=EVENT,
                            headers={"stripe-signature": _sign(EVENT, "wrong-secret")})
    assert r.status_code == 400


def test_webhook_200_on_valid_signature(webhook_client, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", DUMMY)
    r = webhook_client.post("/api/webhooks/stripe", content=EVENT,
                            headers={"stripe-signature": _sign(EVENT, DUMMY)})
    assert r.status_code == 200, r.text


# ---------- billing API keys ----------

@pytest.fixture
def billing_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "billing.db"))
    import billing.main as billing_main
    billing_main = importlib.reload(billing_main)
    return TestClient(billing_main.app)


@pytest.fixture
def allocator_client(monkeypatch):
    import billing.revenue_allocator as ra
    return TestClient(ra.alloc_app)


INVOICE = {"customer_email": "a@example.com", "amount_cents": 100, "description": "t"}


@pytest.mark.parametrize("path,method,body", [
    ("/create-invoice", "post", INVOICE),
    ("/transactions", "get", None),
])
def test_billing_503_when_key_unset(billing_client, monkeypatch, path, method, body):
    monkeypatch.delenv("BILLING_API_KEY", raising=False)
    r = getattr(billing_client, method)(path, **({"json": body} if body else {}),
                                        headers={"X-API-Key": "anything"})
    assert r.status_code == 503


@pytest.mark.parametrize("path,method,body", [
    ("/create-invoice", "post", INVOICE),
    ("/transactions", "get", None),
])
def test_billing_401_on_wrong_or_missing_key(billing_client, monkeypatch, path, method, body):
    monkeypatch.setenv("BILLING_API_KEY", DUMMY)
    kw = {"json": body} if body else {}
    assert getattr(billing_client, method)(path, **kw).status_code == 401
    assert getattr(billing_client, method)(path, **kw, headers={"X-API-Key": "nope"}).status_code == 401


def test_transactions_ok_with_key(billing_client, monkeypatch):
    monkeypatch.setenv("BILLING_API_KEY", DUMMY)
    r = billing_client.get("/transactions", headers={"X-API-Key": DUMMY})
    assert r.status_code == 200 and r.json() == []
    r = billing_client.get("/transactions", headers={"Authorization": f"Bearer {DUMMY}"})
    assert r.status_code == 200


def test_create_invoice_with_key_still_needs_gar530_approval(billing_client, monkeypatch, gate_env):
    """API key alone is not enough: the GAR-530 approval gate still applies (403)."""
    monkeypatch.setenv("BILLING_API_KEY", DUMMY)
    r = billing_client.post("/create-invoice", json=INVOICE, headers={"X-API-Key": DUMMY})
    assert r.status_code == 403


def test_health_stays_open(billing_client, monkeypatch):
    monkeypatch.delenv("BILLING_API_KEY", raising=False)
    assert billing_client.get("/health").status_code == 200


PAYOUT = {"amount_cents": 1000}


def test_allocate_execute_503_when_key_unset(allocator_client, monkeypatch):
    monkeypatch.delenv("ALLOCATOR_API_KEY", raising=False)
    r = allocator_client.post("/allocate/execute", json=PAYOUT, headers={"X-API-Key": "x"})
    assert r.status_code == 503


def test_allocate_execute_401_on_bad_key(allocator_client, monkeypatch):
    monkeypatch.setenv("ALLOCATOR_API_KEY", DUMMY)
    assert allocator_client.post("/allocate/execute", json=PAYOUT).status_code == 401
    assert allocator_client.post("/allocate/execute", json=PAYOUT,
                                 headers={"X-API-Key": DUMMY + "x"}).status_code == 401


def test_allocate_execute_with_key_still_needs_gar530_approval(allocator_client, monkeypatch, gate_env):
    monkeypatch.setenv("ALLOCATOR_API_KEY", DUMMY)
    r = allocator_client.post("/allocate/execute", json=PAYOUT, headers={"X-API-Key": DUMMY})
    assert r.status_code == 403


def test_allocate_preview_stays_open(allocator_client, monkeypatch):
    """/allocate only does math (no transfers), so it is unchanged."""
    monkeypatch.delenv("ALLOCATOR_API_KEY", raising=False)
    assert allocator_client.post("/allocate", json=PAYOUT).status_code == 200
