"""GAR-530: every real send/charge/transfer site refuses before the network call.

Each network primitive is monkeypatched to a recorder. Without an approval the
recorder must never fire; with a valid approval it fires exactly once (per action).
"""
import asyncio
import importlib
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from approval_gate import ApprovalRequired
from conftest import read_events

EMAIL = "lead@example.com"


class Recorder:
    def __init__(self, result=None):
        self.calls = []
        self.result = result

    def __call__(self, *a, **kw):
        self.calls.append((a, kw))
        return self.result


class _Resp:
    status = 202

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return b"{}"


# ── G1 backend/nurture.py send_email (SMTP) ──

class FakeSMTP:
    instances = []

    def __init__(self, *a, **kw):
        self.sent = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def ehlo(self):
        pass

    def starttls(self, **kw):
        pass

    def login(self, *a):
        pass

    def sendmail(self, *a):
        self.sent.append(a)


@pytest.fixture
def nurture(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    mod = importlib.import_module("nurture")
    monkeypatch.setattr(mod, "SMTP_USER", "user")
    monkeypatch.setattr(mod, "SMTP_PASS", "pass")
    FakeSMTP.instances = []
    monkeypatch.setattr(mod.smtplib, "SMTP", FakeSMTP)
    return mod


def test_g1_nurture_refuses_without_id(gate_env, nurture):
    out = nurture.send_email(EMAIL, "s", "<p>h</p>", "t")
    assert out["status"] == "refused" and "missing_id" in out["message"]
    assert FakeSMTP.instances == []
    assert read_events(gate_env)[-1]["event_type"] == "policy.action.refused.v1"


def test_g1_nurture_sends_once_with_id(gate_env, grant, nurture):
    pid = grant("--action", "send.email", "--to", EMAIL)
    assert nurture.send_email(EMAIL, "s", "<p>h</p>", "t", approval_id=pid)["status"] == "sent"
    assert sum(len(s.sent) for s in FakeSMTP.instances) == 1
    assert nurture.send_email(EMAIL, "s", "<p>h</p>", "t", approval_id=pid)["status"] == "refused"
    assert sum(len(s.sent) for s in FakeSMTP.instances) == 1


def test_g1_refused_steps_stay_pending(gate_env, nurture, monkeypatch):
    step = SimpleNamespace(status="pending", lead=SimpleNamespace(status="new", email=EMAIL, name="L"),
                           template=SimpleNamespace(subject="s", body_html="h", body_text="t"))
    query = SimpleNamespace(filter=lambda *a: query, order_by=lambda *a: query,
                            limit=lambda *a: query, all=lambda: [step])
    db = SimpleNamespace(query=lambda *a: query, commit=lambda: None)
    monkeypatch.setattr(nurture, "render_template", lambda t, lead: t)
    monkeypatch.setattr(nurture, "NurtureStep", _ColumnStub())
    results = nurture.process_nurture_queue(db)
    assert results["refused"] == 1 and results["sent"] == 0
    assert step.status == "pending" and step.lead.status == "new"
    assert FakeSMTP.instances == []


class _ColumnStub:
    class _Col:
        def __eq__(self, other):
            return True

        def __le__(self, other):
            return True

        __hash__ = object.__hash__

    status = _Col()
    scheduled_at = _Col()


# ── G2 backend/rhns_audit.py send_audit_report (SendGrid) ──

@pytest.fixture
def rhns(monkeypatch):
    mod = importlib.import_module("rhns_audit")
    monkeypatch.setattr(mod, "SENDGRID_API_KEY", "placeholder")
    rec = Recorder(_Resp())
    monkeypatch.setattr(mod.urllib.request, "urlopen", rec)
    return mod, rec


def test_g2_audit_report_refuses_without_id(gate_env, rhns):
    mod, rec = rhns
    assert mod.send_audit_report(EMAIL, "L", "Co", "<p/>") is False
    assert rec.calls == []


def test_g2_audit_report_sends_once_with_id(gate_env, grant, rhns):
    mod, rec = rhns
    pid = grant("--action", "send.email", "--to", EMAIL)
    assert mod.send_audit_report(EMAIL, "L", "Co", "<p/>", approval_id=pid) is True
    assert len(rec.calls) == 1
    assert mod.send_audit_report("someone-else@example.com", "L", "Co", "<p/>", approval_id=pid) is False
    assert len(rec.calls) == 1


# ── G3 agents/sales_fleet/fleet.py send_email (Resend, live only) ──

@pytest.fixture
def fleet(monkeypatch):
    from agents.sales_fleet import config, fleet as mod
    from agents.sales_fleet.leads import Lead

    monkeypatch.setattr(config, "DRY_RUN", False)
    monkeypatch.setattr(config, "RESEND_API_KEY", "placeholder")
    monkeypatch.setattr(config, "APPROVAL_ID", "")
    rec = Recorder(_Resp())
    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", rec)

    def packet(email=EMAIL):
        lead = Lead(company="Co", contact_name="L", email=email, title="Owner",
                    vertical="HVAC", city="Dallas", source="test")
        return mod.OutreachPacket(lead=lead, subject="s", body="b", sku_key="47", sku_url="u", price=47)

    return mod, config, rec, packet


def test_g3_fleet_live_refuses_without_id(gate_env, fleet):
    mod, config, rec, packet = fleet
    p = mod.send_email(packet())
    assert p.sent is False and p.send_error == "approval_required:missing_id"
    assert rec.calls == []


def test_g3_fleet_dry_run_never_reaches_gate(gate_env, fleet, monkeypatch):
    mod, config, rec, packet = fleet
    monkeypatch.setattr(config, "DRY_RUN", True)
    assert mod.send_email(packet()).send_error == "dry_run"
    assert read_events(gate_env) == [] and rec.calls == []


def test_g3_fleet_sends_only_to_approved_recipients(gate_env, grant, fleet, monkeypatch):
    mod, config, rec, packet = fleet
    pid = grant("--action", "send.email", "--to", EMAIL, "--uses", "1")
    monkeypatch.setattr(config, "APPROVAL_ID", pid)
    assert mod.send_email(packet("not-approved@example.com")).send_error == "approval_required:recipient_not_approved"
    assert mod.send_email(packet()).sent is True
    assert len(rec.calls) == 1


# ── G4 billing/main.py create_invoice (PaymentIntent.create) ──

@pytest.fixture
def billing(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "billing.db"))
    sys.modules.pop("billing.main", None)
    mod = importlib.import_module("billing.main")
    intent = SimpleNamespace(id="pi_test", client_secret="cs_test", status="requires_payment_method")
    rec = Recorder(intent)
    monkeypatch.setattr(mod.stripe.PaymentIntent, "create", rec)
    from fastapi.testclient import TestClient

    return TestClient(mod.app), rec


def _invoice(**kw):
    body = {"customer_email": EMAIL, "amount_cents": 4700, "currency": "usd", "description": "audit"}
    body.update(kw)
    return body


def test_g4_invoice_refuses_without_id(gate_env, billing):
    client, rec = billing
    r = client.post("/create-invoice", json=_invoice())
    assert r.status_code == 403 and "missing_id" in r.json()["detail"]
    assert rec.calls == []


def test_g4_invoice_charges_once_with_id_and_respects_cap(gate_env, grant, billing):
    client, rec = billing
    pid = grant("--action", "charge.payment_intent", "--to", EMAIL, "--max-amount-cents", "4700",
                "--currency", "usd")
    assert client.post("/create-invoice", json=_invoice(amount_cents=4701, approval_id=pid)).status_code == 403
    assert rec.calls == []
    assert client.post("/create-invoice", json=_invoice(approval_id=pid)).status_code == 200
    assert client.post("/create-invoice", json=_invoice(approval_id=pid)).status_code == 403
    assert len(rec.calls) == 1


# ── G5 billing/revenue_allocator.py execute_allocation (Transfer.create) ──

@pytest.fixture
def allocator(monkeypatch):
    mod = importlib.import_module("billing.revenue_allocator")
    rec = Recorder(SimpleNamespace(id="tr_test"))
    monkeypatch.setattr(mod.stripe.Transfer, "create", rec)
    monkeypatch.setattr(mod, "DESTINATIONS", {k: f"acct_{k}" for k in mod.ALLOCATION_RULES})
    return mod, rec


def test_g5_allocation_refuses_without_id(gate_env, allocator):
    mod, rec = allocator
    with pytest.raises(ApprovalRequired):
        mod.execute_allocation(10_000)
    assert rec.calls == []
    from fastapi.testclient import TestClient

    r = TestClient(mod.alloc_app).post("/allocate/execute", json={"amount_cents": 10_000})
    assert r.status_code == 403 and rec.calls == []


def test_g5_allocation_transfers_with_id_once(gate_env, grant, allocator):
    mod, rec = allocator
    pid = grant("--action", "money.transfer", "--max-amount-cents", "10000", "--currency", "usd")
    with pytest.raises(ApprovalRequired):
        mod.execute_allocation(10_001, approval_id=pid)
    out = mod.execute_allocation(10_000, approval_id=pid)
    assert {v["status"] for v in out.values()} == {"transferred"}
    assert len(rec.calls) == 4  # one approval covers the 4 buckets of one allocation
    with pytest.raises(ApprovalRequired):
        mod.execute_allocation(10_000, approval_id=pid)
    assert len(rec.calls) == 4


# ── G6 backend/payments.py create_checkout (standing plan approval) ──

@pytest.fixture
def payments(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    mod = importlib.import_module("payments")
    session_rec = Recorder(SimpleNamespace(url="https://checkout.example/s", id="cs_test"))
    customer_rec = Recorder(SimpleNamespace(id="cus_test"))
    fake = SimpleNamespace(checkout=SimpleNamespace(Session=SimpleNamespace(create=session_rec)),
                           Customer=SimpleNamespace(create=customer_rec))
    monkeypatch.setattr(mod, "stripe", fake)
    user = SimpleNamespace(id=1, email=EMAIL, name="L", stripe_customer_id=None)
    db = SimpleNamespace(commit=lambda: None)
    return mod, session_rec, customer_rec, user, db


def test_g6_checkout_refused_without_standing_approval(gate_env, payments):
    mod, session_rec, customer_rec, user, db = payments
    with pytest.raises(HTTPException) as ei:
        mod.create_checkout(mod.CheckoutRequest(plan="starter"), user=user, db=db)
    assert ei.value.status_code == 403
    assert session_rec.calls == [] and customer_rec.calls == []


def test_g6_standing_plan_approval_keeps_pay_button_working(gate_env, grant, payments):
    mod, session_rec, customer_rec, user, db = payments
    grant("--action", "charge.checkout", "--standing", "--plan", "starter",
          "--max-amount-cents", "4900", "--currency", "usd")
    for _ in range(3):
        out = mod.create_checkout(mod.CheckoutRequest(plan="starter"), user=user, db=db)
        assert out["session_id"] == "cs_test"
    assert len(session_rec.calls) == 3
    with pytest.raises(HTTPException) as ei:  # other plans need their own standing approval
        mod.create_checkout(mod.CheckoutRequest(plan="enterprise"), user=user, db=db)
    assert ei.value.status_code == 403 and len(session_rec.calls) == 3


# ── G7 crm/onboarding_pipeline.py send_welcome_email (stub) ──

def test_g7_welcome_email_stub_is_gated(gate_env, grant):
    mod = importlib.import_module("crm.onboarding_pipeline")
    out = asyncio.run(mod.send_welcome_email(EMAIL, "L"))
    assert out["status"] == "refused"
    pid = grant("--action", "send.email", "--to", EMAIL)
    assert asyncio.run(mod.send_welcome_email(EMAIL, "L", approval_id=pid))["status"] == "queued"
