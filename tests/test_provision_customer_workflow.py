"""Regression checks for the guarded manual Vercel deployment workflow.

Run with: python -m unittest tests.test_provision_customer_workflow
These tests inspect source only; they do not call Vercel or exercise GitHub environments.
"""
from pathlib import Path
import unittest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/provision-customer.yml"


class ProvisionWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_no_unapproved_dispatch(self):
        self.assertNotIn("repository_dispatch:", self.text)
        self.assertIn("workflow_dispatch:", self.text)

    def test_environment_gate(self):
        self.assertIn("environment: production", self.text)
        self.assertIn("permissions: {}", self.text)

    def test_fail_closed(self):
        self.assertIn("set -euo pipefail", self.text)
        self.assertIn("curl --fail-with-body", self.text)
        self.assertIn('state" == "READY"', self.text)
        self.assertIn("Deployment not ready before timeout", self.text)

    def test_no_unverified_customer_success(self):
        self.assertNotIn("customer_provisioned", self.text)
        self.assertNotIn("BUTLER_WEBHOOK_URL", self.text)
        self.assertNotIn("client_payload.email", self.text)


if __name__ == "__main__":
    unittest.main()
