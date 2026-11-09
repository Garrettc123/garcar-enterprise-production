from __future__ import annotations

from typing import Any

ALLOWED_LAYERS = frozenset({"Execution", "Revenue", "Knowledge", "Orchestration"})
MAX_AMOUNT_CENTS = 500_000
MAX_AUTOMATED_RISK = 0.35


def evaluate_policy(layer: str, parameters: dict[str, Any], risk_score: float) -> tuple[bool, str]:
    if layer not in ALLOWED_LAYERS:
        return False, "LAYER_NOT_ALLOWED"
    amount = parameters.get("amount_cents", 0)
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
        return False, "INVALID_AMOUNT"
    if amount > MAX_AMOUNT_CENTS:
        return False, "BUDGET_LIMIT_EXCEEDED"
    if not 0.0 <= risk_score <= 1.0:
        return False, "INVALID_RISK_SCORE"
    if risk_score > MAX_AUTOMATED_RISK:
        return False, "RISK_REQUIRES_MANUAL_REVIEW"
    return True, "POLICY_PASSED"
