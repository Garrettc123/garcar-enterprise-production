"""Deterministic, auditable, assumption-driven underwriting."""
from decimal import Decimal, ROUND_HALF_UP
from .models import UnderwritingIn, UnderwritingResult

CENT = Decimal("0.01")

def cents(v: Decimal) -> Decimal:
    return v.quantize(CENT, rounding=ROUND_HALF_UP)

def analyze(asking_price: Decimal, assumptions: UnderwritingIn) -> UnderwritingResult:
    if asking_price < 0:
        raise ValueError("asking price must not be negative")
    selling_cost = assumptions.arv * assumptions.selling_cost_rate
    cost_ex_purchase = (
        selling_cost + assumptions.repairs + assumptions.closing_costs
        + assumptions.holding_costs + assumptions.financing_costs
        + assumptions.reserve + assumptions.buyer_target_profit
        + assumptions.proposed_assignment_fee
    )
    formula_mao = max(Decimal(0), cents(assumptions.arv - cost_ex_purchase))
    rule_mao = max(Decimal(0), cents(assumptions.arv * assumptions.heuristic_arv_fraction - assumptions.repairs))
    mao = min(formula_mao, rule_mao)
    buyer_profit = cents(assumptions.arv - selling_cost - assumptions.repairs - assumptions.closing_costs
                         - assumptions.holding_costs - assumptions.financing_costs - assumptions.reserve
                         - asking_price - assumptions.proposed_assignment_fee)
    headroom = cents(mao - asking_price)
    return UnderwritingResult(
        asking_price=cents(asking_price), formula_mao=formula_mao,
        seventy_percent_rule_mao=rule_mao, maximum_allowable_offer=mao,
        headroom_vs_asking=headroom, estimated_buyer_profit_at_asking=buyer_profit,
        potential_assignment_fee=cents(assumptions.proposed_assignment_fee),
        viable_under_assumptions=(headroom >= 0 and buyer_profit >= assumptions.buyer_target_profit),
    )
