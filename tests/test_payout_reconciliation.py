"""Tests for Stripe payout-event verification and evidence extraction."""
from __future__ import annotations

import pytest
import stripe
from fastapi import HTTPException

from src.stripe_reconciliation import verify_stripe_event


def test_signed_payout_event_exposes_only_reconciliation_fields(monkeypatch):
    event = {
        "id": "evt_payout_1",
        "type": "payout.paid",
        "created": 1793480000,
        "livemode": True,
        "data": {
            "object": {
                "id": "po_123",
                "status": "paid",
                "amount": 12345,
                "currency": "USD",
                "account_number": "must-not-be-copied",
            }
        },
    }
    monkeypatch.setattr(stripe.Webhook, "construct_event", lambda *_args: event)

    result = verify_stripe_event(b"{}", "t=1,v1=test", "whsec_test")

    assert result["event_id"] == "evt_payout_1"
    assert result["payout"] == {
        "payout_id": "po_123",
        "amount_minor": 12345,
        "currency": "usd",
        "status": "paid",
    }
    assert "account_number" not in str(result)
    assert result["funds_moved"] is False
    assert result["reconciliation_state"] == "RECORDED_NOT_ACTIONED"


def test_payout_event_with_invalid_status_is_rejected(monkeypatch):
    event = {
        "id": "evt_payout_2",
        "type": "payout.paid",
        "data": {"object": {"id": "po_124", "status": "pending", "amount": 123, "currency": "USD"}},
    }
    monkeypatch.setattr(stripe.Webhook, "construct_event", lambda *_args: event)

    with pytest.raises(HTTPException) as error:
        verify_stripe_event(b"{}", "t=1,v1=test", "whsec_test")
    assert error.value.status_code == 400


def test_non_payout_events_do_not_expose_payout_values(monkeypatch):
    event = {
        "id": "evt_customer_1",
        "type": "customer.created",
        "data": {"object": {"id": "cus_1", "status": "active", "amount": 1000, "currency": "USD"}},
    }
    monkeypatch.setattr(stripe.Webhook, "construct_event", lambda *_args: event)

    result = verify_stripe_event(b"{}", "t=1,v1=test", "whsec_test")

    assert "payout" not in result
    assert result["object_id"] == "cus_1"
