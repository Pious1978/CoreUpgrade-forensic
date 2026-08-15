from typing import List
from research.adapter import ResearchCandidate
from .base import BasePromotionPolicy, PromotionDecision

class InstitutionalThresholdPolicy(BasePromotionPolicy):
    def __init__(self, min_score: float = 0.80, min_confidence: float = 0.85, min_liquidity: float = 0.90, max_volatility: float = 0.75):
        self.min_score = min_score
        self.min_confidence = min_confidence
        self.min_liquidity = min_liquidity
        self.max_volatility = max_volatility

    def evaluate(self, candidate: ResearchCandidate) -> PromotionDecision:
        reasons = []
        
        if candidate.score < self.min_score:
            reasons.append(f"Score {candidate.score} below minimum threshold {self.min_score}")
        if candidate.confidence < self.min_confidence:
            reasons.append(f"Confidence {candidate.confidence} below minimum threshold {self.min_confidence}")
        if candidate.liquidity_score < self.min_liquidity:
            reasons.append(f"Liquidity score {candidate.liquidity_score} below minimum threshold {self.min_liquidity}")
        if candidate.volatility_score > self.max_volatility:
            reasons.append(f"Volatility score {candidate.volatility_score} exceeds ceiling {self.max_volatility}")

        is_promoted = len(reasons) == 0
        return PromotionDecision(
            candidate=candidate,
            is_promoted=is_promoted,
            reasons=reasons if reasons else ["Passed all institutional promotion thresholds."]
        )
