from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import pytest
from garcar_reos.models import PropertyIn, EvidenceIn, UnderwritingIn, BuyerIn, DecisionIn
from garcar_reos.store import CaseStore, Conflict

NOW = datetime.now(timezone.utc) - timedelta(minutes=5)

@pytest.fixture
def store(tmp_path):
    return CaseStore(tmp_path / "cases.sqlite")

@pytest.fixture
def case(store):
    return store.add_case(PropertyIn(street_address="10 Oak Road",city="Alvarado", state="TX",postal_code="76009",
                                     county="Johnson",property_type="single_family",asking_price="80000",
                                     source_url="https://example.org/listing",observed_at=NOW))

def uw():
    return UnderwritingIn(arv="200000",repairs="25000",closing_costs="5000",holding_costs="3000",
                          financing_costs="2000",reserve="5000",buyer_target_profit="20000",
                          proposed_assignment_fee="5000",selling_cost_rate="0.08")

def test_duplicate_property_blocked(store, case):
    with pytest.raises(Conflict):
        store.add_case(PropertyIn(street_address="10 OAK Road",city="Alvarado",state="tx",postal_code="76009",
                                  county="Johnson", property_type="single_family",asking_price="90000",
                                  source_url="https://example.org/other",observed_at=NOW))

def test_approval_requires_evidence_and_explicit_decision(store, case):
    uid=case["id"]
    store.run_underwriting(uid, uw())
    decision = DecisionIn(decision="approve_research", reviewer="Operations lead", rationale="Reviewed sourced assumptions for further research")
    with pytest.raises(Conflict):
        store.decide(uid, decision)
    for field in ("asking_price", "arv", "repairs", "ownership"):
        store.add_evidence(uid, EvidenceIn(field=field, source_url="https://example.org/source", observed_at=NOW,
                                           note="Operator read supporting public source", reviewed_by="Operations lead"))
    assert store.readiness(uid)["ready_for_research_approval"]
    result = store.decide(uid, decision)
    assert result["review_status"] == "research_approved"
    assert store.get_case(uid)["review_status"] == "research_approved"
    assert store.verify_audit()["valid"]

def test_stale_evidence_does_not_pass(store, case):
    uid = case["id"]
    store.run_underwriting(uid, uw())
    old = NOW-timedelta(days=91)
    for field in ("asking_price", "arv", "repairs", "ownership"):
        store.add_evidence(uid,EvidenceIn(field=field,source_url="https://example.org/a", observed_at=old,
                                         reviewed_by="Operator",note="Old original review"))
    assert not store.readiness(uid)["ready_for_research_approval"]

def test_buyer_preliminary_match(store, case):
    buyer = store.add_buyer(BuyerIn(label="Sample buyer criterion record",counties=["Johnson"],
                                    property_types=["single_family"], max_acquisition_price="100000",
                                    criteria_source_url="https://example.org/criteria",verified_at=NOW,
                                    status="criteria_reviewed"))
    matches=store.match_buyers(case["id"])
    assert len(matches)==1 and matches[0]["buyer_id"]==buyer["id"]
    assert matches[0]["match_type"] == "preliminary_criteria_only"

def test_reject_always_possible(store, case):
    result=store.decide(case["id"],DecisionIn(decision="reject_research",reviewer="Operator",rationale="Unverifiable supporting data"))
    assert result["review_status"] == "research_rejected"

def test_detects_audit_alteration(store, case):
    with sqlite3.connect(store.path) as db:
        db.execute("UPDATE audit SET event_hash=? WHERE seq=1", ("a"*64,))
    assert not store.verify_audit()["valid"]
