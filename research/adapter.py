from dataclasses import dataclass

@dataclass(frozen=True)
class ResearchCandidate:
    symbol: str
    score: float
    confidence: float
    momentum_score: float
    liquidity_score: float
    quality_score: float
    volatility_score: float
