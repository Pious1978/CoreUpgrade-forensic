from dataclasses import dataclass

@dataclass(frozen=True)
class ResearchPromotionPolicy:
    minimum_confidence: float = 0.60
    minimum_history_days: int = 30
    minimum_liquidity_usd: float = 1_000_000.0

    def evaluate(self, confidence: float) -> bool:
        return confidence >= self.minimum_confidence
