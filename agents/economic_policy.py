"""Economic objective functions for governed autonomous agents."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class EconomicScore:
    expected_value: float
    probability: float
    cost: float
    risk_penalty: float
    score: float

def score_opportunity(expected_value: float, probability: float,
                      cost: float = 0.0, risk_penalty: float = 0.0) -> EconomicScore:
    value = max(0.0, expected_value) * max(0.0, min(1.0, probability))
    score = value - max(0.0, cost) - max(0.0, risk_penalty)
    return EconomicScore(max(0.0, expected_value), max(0.0, min(1.0, probability)),
                         max(0.0, cost), max(0.0, risk_penalty), score)

def should_pursue(score: EconomicScore, minimum_score: float = 0.0) -> bool:
    """Economic filter only; safety policy remains authoritative elsewhere."""
    return score.score >= minimum_score
