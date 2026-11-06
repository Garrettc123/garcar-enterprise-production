"""Regression checks for production-facing claims. No external services required."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source(path):
    return (ROOT / path).read_text(encoding="utf-8")


class NoSyntheticProductionClaimsTests(unittest.TestCase):
    def test_patched_modules_parse(self):
        for path in [
            "money_flow_loop/stages/trust.py",
            "money_flow_loop/stages/trial.py",
            "money_flow_loop/stages/referral.py",
            "money_flow_loop/stages/attention.py",
            "money_flow_loop/orchestrator.py",
            "money_flow_loop/api.py",
            "money_flow_loop/stages/expansion.py",
            "money_flow_loop/stages/conversion.py",
            "backend/payments.py",
            "backend/rhns_audit.py",
            "crm/nurture_sequence.py",
        ]:
            with self.subTest(path=path):
                ast.parse(source(path), filename=path)

    def test_fake_trust_metrics_are_not_published(self):
        value = source("money_flow_loop/stages/trust.py")
        self.assertIn('"evidence_unavailable"', value)
        self.assertIn('"live_proof": None', value)
        self.assertNotIn('"active_businesses_this_week": 47', value)
        self.assertNotIn('"bookings_handled_last_24h": 312', value)

    def test_trial_never_claims_access_without_receipt(self):
        value = source("money_flow_loop/stages/trial.py")
        self.assertIn('"not_provisioned"', value)
        self.assertNotIn('"trial_live"', value)

    def test_no_synthetic_prospect_email(self):
        value = source("money_flow_loop/stages/attention.py")
        self.assertNotIn("@garcar.internal", value)
        self.assertIn('raise ValueError("A contact email is required;', value)

    def test_no_fabricated_referral_program(self):
        value = source("money_flow_loop/stages/referral.py")
        self.assertNotIn("https://garcar.enterprise", value)
        self.assertIn('"referral_link": None', value)

    def test_sales_drafts_are_manually_reviewed(self):
        tree = ast.parse(source("crm/nurture_sequence.py"))
        assignment = next(
            n for n in tree.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "NURTURE_SEQUENCE"
                    for t in n.targets)
        )
        drafts = ast.literal_eval(assignment.value)
        self.assertTrue(drafts)
        self.assertTrue(all(d.get("requires_operator_approval") is True for d in drafts))
        combined = " ".join(d["body"] for d in drafts)
        for banned in ["[CALENDLY_LINK]", "$2,200/month recovered", "in their words"]:
            self.assertNotIn(banned, combined)

    def test_expansion_is_unverified(self):
        value = source("money_flow_loop/stages/expansion.py")
        self.assertIn('"status": "evidence_unavailable"', value)
        self.assertIn('"roi": None', value)
        self.assertIn('"churn_risk": None', value)
        self.assertIn('"money_events": []', value)
        for forbidden in ['"roi": 3.4', '"usage_percentile": 0.82',
                          '"churn_risk": 0.12', '"estimated_mrr_lift": 100.0']:
            self.assertNotIn(forbidden, value)

    def test_lead_endpoint_rejects_unknown_identity(self):
        value = source("money_flow_loop/api.py")
        self.assertIn('status_code=422', value)

    def test_paid_checkout_requires_confirmation(self):
        value = source("backend/payments.py")
        self.assertIn('data.get("payment_status") != "paid"', value)
        self.assertIn('if user_id and plan in PLANS:', value)
        self.assertNotIn('"https://buy.stripe.com/garcar-recovery-sprint"', value)

    def test_unverified_rhns_audit_cannot_be_generated(self):
        value = source("backend/rhns_audit.py")
        self.assertIn('"requires_verified_data_and_manual_fulfillment"', value)
        for forbidden in ['"$1-5M"', '"$40-120K/year"',
                          "The three leaks above are not independent",
                          "Auto-generated audit for"]:
            self.assertNotIn(forbidden, value)

    def test_controller_does_not_claim_live_cash_flow(self):
        value = source("money_flow_loop/orchestrator.py")
        self.assertIn('"initialized_unverified"', value)
        self.assertNotIn('"organism_alive"', value)


if __name__ == "__main__":
    unittest.main()
