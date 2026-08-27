from typing import List
from .base import BaseScanner
from research.adapter import ResearchCandidate

class MomentumScanner(BaseScanner):
    def scan(self) -> List[ResearchCandidate]:
        return [
            ResearchCandidate(
                symbol="NVDA",
                score=0.92,
                confidence=0.89,
                momentum_score=0.95,
                liquidity_score=0.98,
                quality_score=0.85,
                volatility_score=0.70
            ),
            ResearchCandidate(
                symbol="MSFT",
                score=0.88,
                confidence=0.87,
                momentum_score=0.85,
                liquidity_score=0.95,
                quality_score=0.90,
                volatility_score=0.65
            ),
            ResearchCandidate(
                symbol="AAPL",
                score=0.85,
                confidence=0.82,  # Fails confidence threshold (0.82 < 0.85)
                momentum_score=0.80,
                liquidity_score=0.99,
                quality_score=0.90,
                volatility_score=0.60
            )
        ]
