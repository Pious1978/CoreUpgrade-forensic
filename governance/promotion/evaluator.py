from typing import List
from research.adapter import ResearchCandidate
from .rules import (
    BasePromotionRule, 
    ConfidenceGateRule, 
    LiquidityGateRule, 
    VolatilityRiskGateRule, 
    QualityGateRule,
    UniverseGateRule
)
from .result import PromotionResult

class MultiFactorPromotionEvaluator:
    def __init__(self, rules: List[BasePromotionRule] = None):
        self.rules = rules or [
            ConfidenceGateRule(),
            LiquidityGateRule(),
            VolatilityRiskGateRule(),
            QualityGateRule(),
            UniverseGateRule()  # <--- Integrated Universe Check
        ]

    def evaluate_candidate(self, candidate: ResearchCandidate) -> PromotionResult:
        reasons = []
        failed_rules = []
        approved = True

        for rule in self.rules:
            passed, message = rule.evaluate(candidate)
            if passed:
                reasons.append(f"PASS: {message}")
            else:
                approved = False
                failed_rules.append(rule.__class__.__name__)
                reasons.append(f"FAIL: {message}")

        return PromotionResult(
            symbol=candidate.symbol,
            approved=approved,
            reasons=reasons,
            failed_rules=failed_rules,
            score=candidate.score
        )
