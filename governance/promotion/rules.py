from abc import ABC, abstractmethod
from research.adapter import ResearchCandidate
from research.universe.registry import InvestmentUniverseRegistry

class BasePromotionRule(ABC):
    @abstractmethod
    def evaluate(self, candidate: ResearchCandidate) -> tuple[bool, str]:
        pass

class ConfidenceGateRule(BasePromotionRule):
    def __init__(self, min_confidence: float = 0.85):
        self.min_confidence = min_confidence

    def evaluate(self, candidate: ResearchCandidate) -> tuple[bool, str]:
        if candidate.confidence >= self.min_confidence:
            return True, f"Confidence {candidate.confidence} meets threshold {self.min_confidence}"
        return False, f"Confidence {candidate.confidence} below threshold {self.min_confidence}"

class LiquidityGateRule(BasePromotionRule):
    def __init__(self, min_liquidity: float = 0.90):
        self.min_liquidity = min_liquidity

    def evaluate(self, candidate: ResearchCandidate) -> tuple[bool, str]:
        if candidate.liquidity_score >= self.min_liquidity:
            return True, f"Liquidity {candidate.liquidity_score} meets threshold {self.min_liquidity}"
        return False, f"Liquidity {candidate.liquidity_score} below threshold {self.min_liquidity}"

class VolatilityRiskGateRule(BasePromotionRule):
    def __init__(self, max_volatility: float = 0.75):
        self.max_volatility = max_volatility

    def evaluate(self, candidate: ResearchCandidate) -> tuple[bool, str]:
        if candidate.volatility_score <= self.max_volatility:
            return True, f"Volatility {candidate.volatility_score} within ceiling {self.max_volatility}"
        return False, f"Volatility {candidate.volatility_score} exceeds ceiling {self.max_volatility}"

class QualityGateRule(BasePromotionRule):
    def __init__(self, min_quality: float = 0.80):
        self.min_quality = min_quality

    def evaluate(self, candidate: ResearchCandidate) -> tuple[bool, str]:
        if candidate.quality_score >= self.min_quality:
            return True, f"Quality score {candidate.quality_score} meets threshold {self.min_quality}"
        return False, f"Quality score {candidate.quality_score} below threshold {self.min_quality}"

class UniverseGateRule(BasePromotionRule):
    def __init__(self, registry: InvestmentUniverseRegistry = None):
        self.registry = registry or InvestmentUniverseRegistry()

    def evaluate(self, candidate: ResearchCandidate) -> tuple[bool, str]:
        if self.registry.is_eligible(candidate.symbol):
            asset = self.registry.get_asset(candidate.symbol)
            return True, f"Symbol {candidate.symbol} is active in registry (Exchange: {asset.exchange})"
        return False, f"Symbol {candidate.symbol} is missing or inactive in the investment universe registry."
