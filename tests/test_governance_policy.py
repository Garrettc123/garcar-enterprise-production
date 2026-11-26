import pytest

from src.governance.policy import evaluate_policy


@pytest.mark.parametrize("layer", ["Execution", "Revenue", "Knowledge", "Orchestration"])
def test_allowed_layers_pass_when_other_constraints_pass(layer):
    assert evaluate_policy(layer, {"amount_cents": 1000}, 0.2) == (True, "POLICY_PASSED")


@pytest.mark.parametrize("layer", ["Admin", "Unknown", "execution", ""])
def test_unrecognized_layers_fail_closed(layer):
    assert evaluate_policy(layer, {"amount_cents": 1000}, 0.2) == (False, "LAYER_NOT_ALLOWED")


def test_amount_over_limit_is_rejected():
    assert evaluate_policy("Revenue", {"amount_cents": 500001}, 0.2) == (False, "BUDGET_LIMIT_EXCEEDED")


@pytest.mark.parametrize("amount", [-1, 1.5, True, "100"])
def test_non_integer_or_negative_amount_is_rejected(amount):
    assert evaluate_policy("Revenue", {"amount_cents": amount}, 0.2) == (False, "INVALID_AMOUNT")


def test_risk_above_automated_threshold_fails_closed():
    assert evaluate_policy("Execution", {}, 0.36) == (False, "RISK_REQUIRES_MANUAL_REVIEW")


def test_risk_outside_range_is_rejected():
    assert evaluate_policy("Execution", {}, 1.1) == (False, "INVALID_RISK_SCORE")
