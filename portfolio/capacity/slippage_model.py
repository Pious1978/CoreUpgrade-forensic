from typing import List
from portfolio.capacity.market_impact import MarketImpactModel
from contracts.execution_report import ExecutionReport

class SlippageModel:
    """Computes execution price slippage incorporating impact, volatility, and execution feedback."""

    def __init__(self, impact_model: MarketImpactModel):
        self.impact_model = impact_model
        # Feedback multiplier: 1.0 = theory perfectly matches reality. 
        self.calibration_factor = 1.0 

    def estimate_slippage_bps(self, order_shares: float, adv_shares: float, volatility: float, spread: float) -> float:
        """Estimates forward slippage based on theory adjusted by historical reality."""
        # 1. Pure theoretical impact
        impact_pct = self.impact_model.calculate_impact(order_shares, adv_shares, volatility, spread)
        theoretical_bps = impact_pct * 10000.0
        
        # 2. Reality adjustment (Feedback Loop)
        adjusted_bps = theoretical_bps * self.calibration_factor
        
        return float(round(adjusted_bps, 2))

    def update_from_execution_reports(self, reports: List[ExecutionReport], expected_bps: float) -> None:
        """Feedback loop: adjust capacity model based on actual vs. expected slippage."""
        if not reports or expected_bps <= 0:
            return
            
        avg_realized = sum(r.slippage_bps for r in reports) / len(reports)
        
        # Ratio of Reality to Theory (e.g., if we expected 10 and got 30, ratio is 3.0)
        reality_ratio = avg_realized / expected_bps
        
        # Smooth the update using an Exponential Moving Average (30% reality, 70% memory)
        self.calibration_factor = (self.calibration_factor * 0.7) + (reality_ratio * 0.3)
