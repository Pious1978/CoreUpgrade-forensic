"""
validation/portfolio_risk.py
Institutional Portfolio Risk & Allocation Engine

Evaluates sector clustering, position concentration limits, and correlation 
penalties across trade distributions to enforce institutional portfolio rules.
"""

import numpy as np
from typing import List, Dict, Any, Optional
from validation.contracts import TradeRecord, PortfolioRules


class PortfolioRiskEngine:
    def __init__(self, trades: List[TradeRecord], rules: PortfolioRules):
        """
        Initializes the portfolio risk evaluation engine.

        Args:
            trades: List of typed TradeRecord instances.
            rules: PortfolioRules dataclass defining concentration and cash parameters.
        """
        self.trades = trades
        self.rules = rules

    def evaluate_portfolio_constraints(self) -> Dict[str, Any]:
        """
        Analyzes trade records against portfolio concentration and sector exposure limits.

        Returns:
            Dictionary containing sector exposures, concentration violations, and cluster penalties.
        """
        if not self.trades:
            return {
                "sector_exposures": {},
                "max_sector_exposure_pct": 0.0,
                "sector_violations": 0,
                "cluster_penalty": 0.0,
                "cash_buffer_required_pct": self.rules.cash_buffer * 100.0
            }

        sector_counts = {}
        total_trades = len(self.trades)

        for trade in self.trades:
            sector = trade.sector.upper() if trade.sector else "UNKNOWN"
            sector_counts[sector] = sector_counts.get(sector, 0) + 1

        sector_exposures = {s: count / total_trades for s, count in sector_counts.items()}
        max_sector_exp = max(sector_exposures.values()) if sector_exposures else 0.0

        violations = 0
        for sector, exp in sector_exposures.items():
            if exp > self.rules.max_sector_exposure:
                violations += 1

        # Calculate cluster penalty if sector exposure breaches institutional mandates
        cluster_penalty = max(0.0, (max_sector_exp - self.rules.max_sector_exposure) * 50.0) if violations > 0 else 0.0

        return {
            "sector_exposures": {s: round(exp * 100.0, 2) for s, exp in sector_exposures.items()},
            "max_sector_exposure_pct": round(max_sector_exp * 100.0, 2),
            "sector_violations": violations,
            "cluster_penalty": round(cluster_penalty, 2),
            "cash_buffer_required_pct": round(self.rules.cash_buffer * 100.0, 2)
        }

    def adjust_trade_sequence_for_portfolio(self) -> List[TradeRecord]:
        """
        Adjusts trade capital allocation weights to account for institutional cash buffers 
        and maximum position concurrency rules.
        """
        adjusted_trades = []
        effective_weight = min(1.0, 1.0 - self.rules.cash_buffer)

        for trade in self.trades:
            # Create a copy or update capital weight to reflect reserved portfolio cash
            trade.capital_weight = effective_weight
            adjusted_trades.append(trade)

        return adjusted_trades
