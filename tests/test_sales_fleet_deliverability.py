"""Regression tests: real-only lead sourcing and no-contact on bounced recipients."""
from agents.sales_fleet import config, fleet, leads
from agents.sales_fleet.suppression import suppression_reason


def test_no_fabricated_seed_leads(monkeypatch):
    monkeypatch.delenv("FLEET_LEAD_JSON", raising=False)
    monkeypatch.delenv("APOLLO_API_KEY", raising=False)
    assert leads.source_leads(limit=25) == []


def test_confirmed_delivery_failure_is_suppressed_case_insensitively():
    # Actual hard delivery failure recorded in Gmail November 19, 2026.
    assert suppression_reason("  CONTACT@TARRANTROOFING.COM ") == "delivery_failure_suppressed"
    assert suppression_reason("garrett@garcar.io") == "delivery_failure_suppressed"


def test_operator_blocklist_and_invalid_address(monkeypatch):
    monkeypatch.setenv("FLEET_SUPPRESSED_EMAILS", " blocked@example.com ")
    monkeypatch.setenv("FLEET_SUPPRESSED_DOMAINS", "example.org")
    assert suppression_reason("blocked@example.com") == "operator_suppressed"
    assert suppression_reason("contact@example.org") == "operator_suppressed_domain"
    assert suppression_reason("bad address@example.com") == "invalid_email"
    assert suppression_reason("valid@example.net") is None
    assert suppression_reason(None) == "no_email"


def test_refused_send_never_checks_approval_or_network(monkeypatch):
    monkeypatch.setattr(config, "DRY_RUN", False)
    monkeypatch.setattr(config, "RESEND_API_KEY", "unit-test-key")

    def should_not_be_called(*args, **kwargs):
        raise AssertionError("approval/network pathway reached for suppressed recipient")

    monkeypatch.setattr(fleet, "require_approval", should_not_be_called)
    packet = fleet.OutreachPacket(
        lead=leads.Lead(
            company="Known bounce", contact_name="Contact",
            email="contact@allianceroofingdfw.com", title="Owner",
            vertical="roofing", city="Dallas", source="test",
        ),
        subject="Test", body="Test", sku_key="497", sku_url="test", price=497,
    )
    result = fleet.send_email(packet)
    assert result.sent is False
    assert result.send_error == "delivery_failure_suppressed"
