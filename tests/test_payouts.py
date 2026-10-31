import pytest
import src.payouts as payouts

def test_non_payout_event_is_ignored(monkeypatch):
    monkeypatch.setattr(payouts, "seal_record", lambda *a, **k: pytest.fail("must not write"))
    assert payouts.record_verified_payout({"type": "customer.created"}, bucket="b", region="r", retention_days=1) == {"result": "ignored"}

def test_payout_requires_event_id():
    event = {"type": "payout.paid", "data": {"object": {"id": "po_1", "status": "paid", "amount": 500, "currency": "usd"}}}
    with pytest.raises(ValueError):
        payouts.record_verified_payout(event, bucket="b", region="r", retention_days=1)

def test_payout_seals_minor_units_and_event_id(monkeypatch):
    captured = {}
    def fake_seal(record, bucket, region, retention_days):
        captured.update(record)
        return {"result": "sealed"}
    monkeypatch.setattr(payouts, "seal_record", fake_seal)
    event = {"id": "evt_1", "type": "payout.paid", "data": {"object": {"id": "po_1", "status": "paid", "amount": 1234, "currency": "USD"}}}
    result = payouts.record_verified_payout(event, bucket="b", region="r", retention_days=30)
    assert result == {"result": "sealed"}
    assert captured["event_id"] == "evt_1"
    assert captured["amount_minor"] == 1234
    assert captured["currency"] == "usd"
