from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from garcar_reos.api import create_app

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("REOS_API_KEY", "operator-key-for-testing")
    monkeypatch.setenv("REOS_APPROVER_KEY", "separate-approver-key")
    monkeypatch.setenv("REOS_DB_PATH", str(tmp_path / "api.sqlite"))
    with TestClient(create_app()) as c:
        yield c

def test_auth_and_health(client):
    assert client.get("/health").status_code == 200
    assert client.get("/v1/cases").status_code == 401
    assert client.get("/v1/cases",headers={"x-api-key":"wrong"}).status_code == 401
    assert client.get("/v1/cases",headers={"x-api-key":"operator-key-for-testing"}).json() == []

def test_source_to_underwriting_to_research_gate(client):
    headers={"x-api-key":"operator-key-for-testing"}
    prop = dict(street_address="99 Meadow Lane",city="Cleburne",state="TX",postal_code="76033",
                county="Johnson",property_type="single_family",asking_price="80000",
                source_url="https://example.org/public-record",
                observed_at=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat())
    r=client.post("/v1/cases",json=prop,headers=headers)
    assert r.status_code==201, r.text
    uid=r.json()["id"]
    uw=dict(arv="200000",repairs="25000", closing_costs="5000",holding_costs="3000",
            financing_costs="2000",reserve="5000",buyer_target_profit="20000",
            proposed_assignment_fee="5000",selling_cost_rate="0.08")
    r=client.post(f"/v1/cases/{uid}/underwrite",json=uw,headers=headers)
    assert r.status_code==201, r.text
    assert r.json()["result"]["maximum_allowable_offer"] == "115000.00"
    decision=dict(decision="approve_research", reviewer="Operations lead",
                  rationale="Operator checked all required research evidence")
    assert client.post(f"/v1/cases/{uid}/research-decision",json=decision,headers=headers).status_code==403
    headers["x-approver-key"]="separate-approver-key"
    assert client.post(f"/v1/cases/{uid}/research-decision",json=decision,headers=headers).status_code==409
    assert client.get("/v1/audit/verify",headers=headers).json()["valid"]
