"""Regression fixtures only: no Stripe events, charges, or production revenue."""
from __future__ import annotations
import json
import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from enterprise.api import app
from enterprise.contracts import BadHandoff, parse_handoff

KEY = "a" * 48
def sample():
    return {"event": "garcar.payment.received", "payment_reference": "pi_fixture_only",
            "idempotency_key": "pi_fixture_only", "amount_minor": 49700,
            "currency": "usd", "sku": "MLS-497", "offer_name": "review",
            "customer_email": "fixture@example.invalid", "created_at": "2026-11-26T00:00:00Z",
            "fulfill_hours": 48}
def body(obj):
    return json.dumps(obj).encode("utf-8")
class ContractTests(unittest.TestCase):
    def test_valid_payload(self):
        msg, digest = parse_handoff(body(sample()), "pi_fixture_only")
        self.assertEqual(msg["sku"], "MLS-497")
        self.assertEqual(len(digest), 64)
    def test_replay_key_mismatch(self):
        with self.assertRaises(BadHandoff):
            parse_handoff(body(sample()), "not-the-reference")
    def test_rejects_duplicate_json_keys(self):
        with self.assertRaises(BadHandoff):
            parse_handoff(b'{"event":1,"event":2}', "pi_fixture_only")
    def test_rejects_untrusted_amounts(self):
        for bad in (-1, 0, True, 49.7, "49700"):
            obj = sample(); obj["amount_minor"] = bad
            with self.subTest(bad=bad), self.assertRaises(BadHandoff):
                parse_handoff(body(obj), "pi_fixture_only")
    def test_rejects_unsupported_events(self):
        obj = sample(); obj["event"] = "stripe.charge.succeeded"
        with self.assertRaises(BadHandoff):
            parse_handoff(body(obj), "pi_fixture_only")
    def test_rejects_oversize(self):
        with self.assertRaises(BadHandoff):
            parse_handoff(b"x" * 32769, "pi_fixture_only")

class APITests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
    def test_healthy_is_not_revenue(self):
        result = self.client.get("/health")
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json()["fulfillment_proven"])
    def test_missing_auth_fails_closed(self):
        with patch.dict(os.environ, {"FULFILLMENT_WEBHOOK_TOKEN": ""}):
            self.assertEqual(self.client.post("/v1/fulfillment", json=sample()).status_code, 503)
    def test_wrong_auth_rejected_without_database(self):
        with patch.dict(os.environ, {"FULFILLMENT_WEBHOOK_TOKEN": KEY}):
            with patch("enterprise.api.record_receipt", side_effect=AssertionError("DB must not be called")):
                result = self.client.post("/v1/fulfillment", json=sample(), headers={"Authorization": "Bearer invalid"})
                self.assertEqual(result.status_code, 401)
    def test_real_receipt_contract_passes_once(self):
        with patch.dict(os.environ, {"FULFILLMENT_WEBHOOK_TOKEN": KEY}):
            with patch("enterprise.api.record_receipt", return_value=True) as store:
                headers={"Authorization": "Bearer " + KEY, "Idempotency-Key": "pi_fixture_only"}
                result=self.client.post("/v1/fulfillment", json=sample(), headers=headers)
                self.assertEqual(result.status_code, 202)
                self.assertEqual(result.json()["processing_status"], "RECEIVED_UNFULFILLED")
                self.assertEqual(store.call_count, 1)
    def test_same_reference_conflicting_payload_rejected(self):
        from enterprise.db import PayloadConflict
        with patch.dict(os.environ, {"FULFILLMENT_WEBHOOK_TOKEN": KEY}):
            with patch("enterprise.api.record_receipt", side_effect=PayloadConflict()):
                result=self.client.post("/v1/fulfillment", json=sample(), headers={
                    "Authorization": "Bearer "+KEY, "Idempotency-Key": "pi_fixture_only"})
                self.assertEqual(result.status_code, 409)
    def test_database_unavailable_fails_closed(self):
        with patch.dict(os.environ, {"FULFILLMENT_WEBHOOK_TOKEN": KEY}):
            with patch("enterprise.api.record_receipt", side_effect=RuntimeError("unavailable")):
                result=self.client.post("/v1/fulfillment", json=sample(), headers={
                    "Authorization": "Bearer "+KEY, "Idempotency-Key": "pi_fixture_only"})
                self.assertEqual(result.status_code, 503)
if __name__ == "__main__":
    unittest.main()
