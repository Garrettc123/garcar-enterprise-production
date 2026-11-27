from decimal import Decimal
import pytest
from pydantic import ValidationError
from garcar_reos.models import UnderwritingIn, PropertyIn
from garcar_reos.underwriting import analyze


def assumptions(**overrides):
    values = dict(arv="200000", repairs="25000", closing_costs="5000", holding_costs="3000",
                  financing_costs="2000", reserve="5000", buyer_target_profit="20000",
                  proposed_assignment_fee="5000", selling_cost_rate="0.08")
    return UnderwritingIn(**(values | overrides))


def test_mao_and_profit_calculation():
    actual = analyze(Decimal("80000"), assumptions())
    assert actual.formula_mao == Decimal("119000.00")
    assert actual.seventy_percent_rule_mao == Decimal("115000.00")
    assert actual.maximum_allowable_offer == Decimal("115000.00")
    assert actual.headroom_vs_asking == Decimal("35000.00")
    assert actual.estimated_buyer_profit_at_asking == Decimal("59000.00")
    assert actual.viable_under_assumptions


def test_asking_exceeds_cap():
    actual = analyze(Decimal("160000"), assumptions())
    assert not actual.viable_under_assumptions
    assert actual.headroom_vs_asking == Decimal("-45000.00")


def test_all_critical_assumptions_required():
    with pytest.raises(ValidationError):
        UnderwritingIn(arv="200000", repairs="1000")


def test_future_source_rejected():
    from datetime import datetime, timedelta, timezone
    with pytest.raises(ValidationError):
        PropertyIn(street_address="1 Main Street", city="Cleburne", state="TX", postal_code="76033",
                   county="Johnson", property_type="single_family", asking_price="10000",
                   source_url="https://example.org/source", observed_at=datetime.now(timezone.utc)+timedelta(days=1))
