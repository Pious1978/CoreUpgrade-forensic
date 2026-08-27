from typing import Any
from .base_policy import BasePromotionPolicy, PolicyEvaluationResult

class ResearchPromotionPolicy(BasePromotionPolicy):
    def __init__(self, min_confidence: float = 0.6) -> None:
        self.min_confidence = min_confidence

    def evaluate(self, source: Any, context: Any) -> PolicyEvaluationResult:
        confidence = getattr(source, "confidence_score", 0.0)
        passed = confidence >= self.min_confidence
        violations = () if passed else ("MIN_CONFIDENCE_THRESHOLD_EXCEEDED",)

        return PolicyEvaluationResult(
            passed=passed,
            score=float(confidence),
            reason="Research confidence check completed." if passed else f"Confidence {confidence} below threshold {self.min_confidence}.",
            violations=violations,
            version="2.3.0"
        )
