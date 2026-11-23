import json

import pytest

from agents.sales_fleet import config
from agents.sales_fleet.fleet import SalesFleet, build_outreach
from agents.sales_fleet.leads import load_env_leads, source_leads


@pytest.fixture(autouse=True)
def no_external_source(monkeypatch):
    monkeypatch.delenv("APOLLO_API_KEY", raising=False)
    monkeypatch.delenv("FLEET_LEAD_JSON", raising=False)


def test_empty_and_short_sources_are_never_padded(monkeypatch):
    assert source_leads() == []
    monkeypatch.setenv("FLEET_LEAD_JSON", '[{"company":"First"}]')
    lead, = source_leads(10)
    assert (lead.title, lead.city, lead.vertical, lead.email) == ("", "", "", None)
    assert not lead.eligible_for_outreach
    assert not source_leads(0)


@pytest.mark.parametrize("bad", ["null", "{}", "not json", "[1]"])
def test_broken_inputs_are_distinct_from_empty_inputs(bad, monkeypatch):
    monkeypatch.setenv("FLEET_LEAD_JSON", bad)
    with pytest.raises(ValueError):
        source_leads()


def test_source_suppression_consent_and_reserved_addresses(monkeypatch):
    row = dict(company="Unit", email="qa@garcar.io", email_status="verified", source_id="unit-row",
               consent_basis="requested_contact")
    for change in ({"source_id": ""}, {"email": "qa@sub.example.org"}, {"email": "atlas+test@garcar.io"},
                   {"consent_basis": ""}, {"is_test": True}, {"source": "seed"}):
        monkeypatch.setenv("FLEET_LEAD_JSON", json.dumps([dict(row, **change)]))
        assert not any(lead.eligible_for_outreach for lead in source_leads())
    monkeypatch.setenv("FLEET_LEAD_JSON", json.dumps([row, dict(row, do_not_contact=True)]))
    assert not source_leads()
    monkeypatch.setenv("FLEET_LEAD_JSON", json.dumps([row, row]))
    lead, = source_leads()
    assert lead.eligible_for_outreach
    assert "buy.stripe.com" not in build_outreach(lead, "2500").body
    with pytest.raises(ValueError):
        SalesFleet("47")


def test_corrupt_ledger_is_preserved(tmp_path, monkeypatch):
    from agents.sales_fleet import fleet
    path = tmp_path / "ledger.json"
    path.write_text("damaged")
    monkeypatch.setattr(config, "LEDGER_PATH", str(path))
    monkeypatch.setattr(fleet, "check_payments_edge", lambda: {"ok": True})
    with pytest.raises(ValueError):
        SalesFleet().run(dry_run=True)
    assert path.read_text() == "damaged"
