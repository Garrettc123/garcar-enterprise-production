"""GAR-530: a scoped approval never covers a request that leaves the scoped field out.

If Garrett caps an approval (max_amount_cents) or pins its currency, a caller that
omits the amount or currency must be refused, not waved through.
"""
import pytest

from approval_gate import ApprovalRequired, require_approval, require_standing_approval


def _reason(fn, *a, **kw):
    with pytest.raises(ApprovalRequired) as ei:
        fn(*a, **kw)
    return ei.value.reason


def test_currency_scoped_approval_refuses_unstated_currency(gate_env, grant):
    pid = grant("--action", "money.transfer", "--max-amount-cents", "5000", "--currency", "usd")
    assert _reason(require_approval, "money.transfer", pid, amount_cents=10) == "missing_currency"
    assert _reason(require_approval, "money.transfer", pid, amount_cents=10, currency="") == "missing_currency"
    require_approval("money.transfer", pid, amount_cents=10, currency="USD")


def test_capped_standing_approval_refuses_unstated_amount(gate_env, grant):
    grant("--action", "charge.checkout", "--standing", "--plan", "starter",
          "--max-amount-cents", "4900", "--currency", "usd")
    assert _reason(require_standing_approval, "charge.checkout", plan="starter",
                   currency="usd") == "missing_amount_cents"
    assert _reason(require_standing_approval, "charge.checkout", plan="starter",
                   amount_cents=4900) == "missing_currency"
    require_standing_approval("charge.checkout", plan="starter", amount_cents=4900, currency="usd")


def test_uncapped_scope_still_needs_no_amount(gate_env, grant):
    # Scopes without a cap/currency keep working for callers that don't pass them.
    pid = grant("--action", "send.email", "--to", "buyer@example.com")
    require_approval("send.email", pid, to="buyer@example.com")
