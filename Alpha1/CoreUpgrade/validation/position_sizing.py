"""
validation/position_sizing.py
Institutional capital allocation and position sizing engine.
Features: Quality score normalization, minimum quality thresholds, 
post-cap exact portfolio heat accounting, initial risk budget auditing,
and full signal lineage traceability.
"""

import logging
from typing import Any, Dict, List, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class PositionSizingEngine:
    """Calculates institutional-grade capital allocations and position sizes

    enforcing minimum quality thresholds, normalized multipliers, exact post-cap
    projected portfolio heat limits, and max position concentration caps.
    """

    def __init__(
        self,
        account_capital: float = 1_000_000.0,
        base_risk_pct: float = 0.01,  # 1% standard account risk per trade
        max_portfolio_heat: float = 0.06,  # Maximum 6% total open risk across portfolio
        max_position_pct: float = 0.20,  # Maximum 20% capital allocation in a single position
        max_invested_pct: float = 0.80,  # Maximum 80% total deployed capital across portfolio
        minimum_quality_score: float = 60.0,  # Minimum quality score required to take a trade
    ) -> None:
        self.account_capital = account_capital
        self.base_risk_pct = base_risk_pct
        self.max_portfolio_heat = max_portfolio_heat
        self.max_position_pct = max_position_pct
        self.max_invested_pct = max_invested_pct
        self.minimum_quality_score = minimum_quality_score

    def calculate_allocation(
        self,
        signal_metrics: Dict[str, Any],
        current_portfolio_heat: float = 0.0,
        current_invested_pct: float = 0.0,
    ) -> Dict[str, Any]:
        """Calculates precise position size and capital allocation for a validated setup.

        Args:
            signal_metrics: Dictionary containing signal_id, setup_name, symbol,
              entry_price, stop_distance_pct, quality_score (0-100 scale), market_regime,
              and liquidity_approved status.
            current_portfolio_heat: Current aggregate risk percentage across open positions.
            current_invested_pct: Current aggregate invested capital weight across portfolio.

        Returns:
            Dict containing approval status, share quantity, capital commitment, dollar risk, and rationale.
        """
        signal_id = signal_metrics.get("signal_id")
        setup_name = signal_metrics.get("setup_name", "UNKNOWN")
        symbol = signal_metrics.get("symbol", "UNKNOWN")
        entry_price = float(signal_metrics.get("entry_price", 0.0))
        stop_distance_pct = float(signal_metrics.get("stop_distance_pct", 0.08))
        quality_score = float(signal_metrics.get("quality_score", 50.0))
        market_regime = signal_metrics.get("market_regime", "BULL")
        liquidity_approved = signal_metrics.get("liquidity_approved", True)

        if entry_price <= 0:
            logger.error(f"Invalid entry price for {symbol}")
            return self._empty_allocation(symbol, signal_id, setup_name, "Invalid entry price")

        # 1. Minimum Quality Filter Check
        if quality_score < self.minimum_quality_score:
            logger.info(
                f"Signal for {symbol} rejected: quality score {quality_score} < threshold {self.minimum_quality_score}."
            )
            return self._empty_allocation(
                symbol, signal_id, setup_name, f"Quality score {quality_score} below minimum threshold"
            )

        # 2. Check liquidity constraints
        if not liquidity_approved:
            logger.info(f"Signal for {symbol} rejected due to liquidity filter failure.")
            return self._empty_allocation(symbol, signal_id, setup_name, "Failed liquidity filter")

        # 3. Normalize Quality Score and Determine Multipliers
        quality_multiplier = quality_score / 100.0
        regime_multipliers = {
            "BULL": 1.2,
            "SIDEWAYS": 0.8,
            "BEAR": 0.4,
            "UNKNOWN": 0.5,
        }
        regime_mult = regime_multipliers.get(market_regime, 0.5)

        # 4. Calculate Initial Planned Risk Budget
        initial_risk_budget_pct = self.base_risk_pct * quality_multiplier * regime_mult
        dollar_risk_allowed = self.account_capital * initial_risk_budget_pct

        # Stop distance per share
        stop_distance_per_share = entry_price * stop_distance_pct
        if stop_distance_per_share <= 0:
            return self._empty_allocation(symbol, signal_id, setup_name, "Invalid stop distance calculation")

        raw_shares_by_risk = dollar_risk_allowed / stop_distance_per_share
        risk_based_capital = raw_shares_by_risk * entry_price

        # 5. Apply Maximum Position Concentration Cap cleanly
        max_capital_allowed = self.account_capital * self.max_position_pct
        allocated_capital = min(risk_based_capital, max_capital_allowed)

        # Recalculate actual deployed risk and shares if concentration cap was triggered
        if allocated_capital < risk_based_capital:
            raw_shares = allocated_capital / entry_price
            dollar_risk_allowed = raw_shares * stop_distance_per_share
            actual_risk_pct = dollar_risk_allowed / self.account_capital
        else:
            raw_shares = raw_shares_by_risk
            actual_risk_pct = initial_risk_budget_pct

        # 6. Check Maximum Deployed Capital and Portfolio Heat Constraints
        projected_invested_pct = current_invested_pct + (allocated_capital / self.account_capital)
        if projected_invested_pct > self.max_invested_pct:
            logger.warning(f"Projected invested capital ({projected_invested_pct:.2%}) exceeds max limit ({self.max_invested_pct:.2%}). Rejection.")
            return self._empty_allocation(symbol, signal_id, setup_name, "Projected max invested capital limit exceeded")

        projected_heat = current_portfolio_heat + actual_risk_pct
        if projected_heat > self.max_portfolio_heat:
            logger.warning(f"Projected portfolio heat ({projected_heat:.2%}) exceeds max limit ({self.max_portfolio_heat:.2%}). Rejection.")
            return self._empty_allocation(symbol, signal_id, setup_name, "Projected portfolio heat limit exceeded")

        shares = int(raw_shares)
        if shares <= 0:
            return self._empty_allocation(symbol, signal_id, setup_name, "Calculated zero shares")

        return {
            "signal_id": signal_id,
            "setup_name": setup_name,
            "symbol": symbol,
            "approved": True,
            "shares": shares,
            "allocated_capital": round(allocated_capital, 2),
            "capital_weight": round(allocated_capital / self.account_capital, 4),
            "dollar_risk": round(dollar_risk_allowed, 2),
            "risk_pct_of_account": round(actual_risk_pct, 4),
            "initial_risk_budget_pct": round(initial_risk_budget_pct, 4),
            "stop_distance_per_share": round(stop_distance_per_share, 4),
            "rationale": {
                "quality_score": quality_score,
                "quality_multiplier": round(quality_multiplier, 4),
                "regime_multiplier": regime_mult,
                "initial_risk_budget_pct": round(initial_risk_budget_pct, 4),
                "actual_risk_pct": round(actual_risk_pct, 4),
                "projected_portfolio_heat": round(projected_heat, 4),
                "projected_invested_pct": round(projected_invested_pct, 4),
            },
        }

    def _empty_allocation(self, symbol: str, signal_id: Optional[str], setup_name: str, reason: str) -> Dict[str, Any]:
        return {
            "signal_id": signal_id,
            "setup_name": setup_name,
            "symbol": symbol,
            "approved": False,
            "shares": 0,
            "allocated_capital": 0.0,
            "capital_weight": 0.0,
            "dollar_risk": 0.0,
            "risk_pct_of_account": 0.0,
            "initial_risk_budget_pct": 0.0,
            "stop_distance_per_share": 0.0,
            "rationale": {"rejection_reason": reason},
        }
