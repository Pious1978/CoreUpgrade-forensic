"""
validation/trade_execution.py
Institutional Execution & Market Friction Simulation Engine.
Features: Side-aware slippage and rejection lineage, square-root non-linear VWAP market impact,
ordered liquidity stress rejections, machine-readable failure taxonomy, commission cost tracking,
actual entry price re-anchoring, and complete T+1 execution audit lineage.
"""

import logging
import uuid
from typing import Any, Dict, Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class TradeExecutionEngine:
    """Simulates institutional-grade order execution, incorporating non-linear VWAP

    market impact, side-dependent slippage, precise liquidity failure taxonomy,
    brokerage commissions, actual fill price tracking, and post-fill risk re-anchoring.
    """

    def __init__(
        self,
        default_order_type: str = "MARKET",  # "MARKET" or "LIMIT"
        max_allowable_spread_pct: float = 0.015,  # Max 1.5% bid-ask spread
        base_slippage_bps: float = 5.0,  # Base slippage in basis points (1 bp = 0.01%)
        commission_bps: float = 10.0,  # Brokerage and exchange fees in basis points (e.g. 0.1%)
    ) -> None:
        self.default_order_type = default_order_type
        self.max_allowable_spread_pct = max_allowable_spread_pct
        self.base_slippage_bps = base_slippage_bps
        self.commission_bps = commission_bps

    def execute_order(
        self,
        allocation_record: Dict[str, Any],
        market_snapshot: Dict[str, Any],
        side: str = "BUY",
    ) -> Dict[str, Any]:
        """Simulates the execution of a validated trade allocation with full institutional realism.

        Args:
            allocation_record: Dictionary containing signal_id, trade_id, symbol,
              shares, allocated_capital, entry_price, signal_date, and stop_price.
            market_snapshot: Dictionary containing current market candle data:
              ['date', 'open', 'high', 'low', 'close', 'volume', 'bid', 'ask', 'avg_daily_volume'].
            side: Execution side ("BUY" or "SELL").

        Returns:
            Dict matching the complete institutional trade execution data contract.
        """
        signal_id = allocation_record.get("signal_id")
        trade_id = allocation_record.get("trade_id", str(uuid.uuid4()))
        symbol = allocation_record.get("symbol", "UNKNOWN")
        intended_shares = int(allocation_record.get("shares", 0))
        target_price = float(allocation_record.get("entry_price", 0.0))

        # T+1 Execution Lineage Dates
        signal_date = allocation_record.get("signal_date", "UNKNOWN")
        order_date = allocation_record.get("order_date", signal_date)
        execution_date = market_snapshot.get("date", order_date)

        stop_price = float(allocation_record.get("stop_price", target_price * 0.92))

        if intended_shares <= 0 or target_price <= 0:
            return self._rejected_execution(
                symbol,
                signal_id,
                trade_id,
                signal_date,
                order_date,
                execution_date,
                "INVALID_ORDER",
                "Zero or negative shares or target price provided",
                side=side,
            )

        # Market Snapshot Extraction
        market_open = float(market_snapshot.get("open", target_price))
        market_high = float(market_snapshot.get("high", target_price))
        market_low = float(market_snapshot.get("low", target_price))
        daily_volume = float(market_snapshot.get("volume", 1_000_000.0))
        adv = float(market_snapshot.get("avg_daily_volume", daily_volume))

        bid = float(market_snapshot.get("bid", market_open * 0.999))
        ask = float(market_snapshot.get("ask", market_open * 1.001))

        mid_price = (bid + ask) / 2.0
        spread_pct = (ask - bid) / mid_price if mid_price > 0 else 0.0

        # 1. Bid-Ask Spread Validation Check
        if spread_pct > self.max_allowable_spread_pct:
            return self._rejected_execution(
                symbol,
                signal_id,
                trade_id,
                signal_date,
                order_date,
                execution_date,
                "SPREAD_TOO_WIDE",
                f"Spread {spread_pct:.2%} exceeds maximum threshold {self.max_allowable_spread_pct:.2%}",
                side=side,
            )

        # 2. Participation Rate & Liquidity Stress Checks
        order_value = intended_shares * target_price
        estimated_daily_turnover = adv * mid_price
        participation_rate = (
            order_value / estimated_daily_turnover if estimated_daily_turnover > 0 else 1.0
        )

        if participation_rate > 0.25:
            return self._rejected_execution(
                symbol,
                signal_id,
                trade_id,
                signal_date,
                order_date,
                execution_date,
                "ADV_LIMIT_BREACH",
                f"Extreme liquidity stress: participation rate {participation_rate:.2%} exceeds 25% ADV limit",
                side=side,
            )

        # 3. Non-Linear Square-Root VWAP Market Impact Model
        spread_cost = spread_pct / 2.0
        impact_cost = (participation_rate**0.5) * 0.0015
        base_slip_cost = self.base_slippage_bps / 10000.0
        total_execution_cost = spread_cost + impact_cost + base_slip_cost

        # Side-Aware Slippage Direction
        if side.upper() == "BUY":
            execution_price = mid_price * (1.0 + total_execution_cost)
        elif side.upper() == "SELL":
            execution_price = mid_price * (1.0 - total_execution_cost)
        else:
            execution_price = mid_price

        # 4. Partial Fill Simulation (Ordered Hierarchy)
        filled_shares = intended_shares
        fill_status = "FILLED"
        if participation_rate > 0.15:
            filled_shares = int(intended_shares * 0.80)
            fill_status = "PARTIAL_FILL"

        # 5. Commission Cost Calculation (P1-2)
        actual_allocated_capital = filled_shares * execution_price
        commission_cost_currency = actual_allocated_capital * (self.commission_bps / 10000.0)

        # 6. Exponentially Calibrated Execution Quality Score
        price_deviation_bps = abs(execution_price - mid_price) / mid_price * 10000.0
        execution_quality_score = max(0.0, 100.0 * np.exp(-price_deviation_bps / 100.0))

        # 7. Execution-Adjusted Risk Re-Anchoring
        if side.upper() == "BUY":
            effective_stop_distance_pct = max(0.0, (execution_price - stop_price) / execution_price)
        else:
            effective_stop_distance_pct = max(0.0, (stop_price - execution_price) / execution_price)

        if side.upper() == "BUY":
            total_slippage_cost = filled_shares * (execution_price - target_price)
        else:
            total_slippage_cost = filled_shares * (target_price - execution_price)

        execution_cost_bps = total_execution_cost * 10000.0

        return {
            "signal_id": signal_id,
            "trade_id": trade_id,
            "symbol": symbol,
            "side": side.upper(),
            "signal_date": str(signal_date),
            "order_date": str(order_date),
            "execution_date": str(execution_date),
            "execution_status": fill_status,
            "intended_shares": intended_shares,
            "filled_shares": filled_shares,
            "fill_ratio": round(filled_shares / intended_shares, 4) if intended_shares > 0 else 0.0,
            "target_price": round(target_price, 4),
            "actual_entry_price": round(execution_price, 4),  # Explicit actual fill price (P1-3)
            "execution_price": round(execution_price, 4),
            "execution_cost_bps": round(execution_cost_bps, 2),
            "commission_cost_currency": round(commission_cost_currency, 2),  # (P1-2)
            "slippage_cost_currency": round(total_slippage_cost, 2),
            "participation_rate": round(participation_rate, 4),
            "execution_quality_score": round(execution_quality_score, 2),
            "effective_stop_distance_pct": round(effective_stop_distance_pct, 4),
            "audit_trail": {
                "order_type": self.default_order_type,
                "spread_pct": round(spread_pct, 4),
                "impact_slippage_bps": round(impact_cost * 10000.0, 2),
                "failure_code": "NONE",
            },
        }

    def _rejected_execution(
        self,
        symbol: str,
        signal_id: Optional[str],
        trade_id: str,
        signal_date: str,
        order_date: str,
        execution_date: str,
        failure_code: str,
        reason: str,
        side: str = "BUY",
    ) -> Dict[str, Any]:
        return {
            "signal_id": signal_id,
            "trade_id": trade_id,
            "symbol": symbol,
            "side": side.upper(),  # Side-aware rejection audit fix (P1-1)
            "signal_date": str(signal_date),
            "order_date": str(order_date),
            "execution_date": str(execution_date),
            "execution_status": "REJECTED",
            "intended_shares": 0,
            "filled_shares": 0,
            "fill_ratio": 0.0,
            "target_price": 0.0,
            "actual_entry_price": 0.0,
            "execution_price": 0.0,
            "execution_cost_bps": 0.0,
            "commission_cost_currency": 0.0,
            "slippage_cost_currency": 0.0,
            "participation_rate": 0.0,
            "execution_quality_score": 0.0,
            "effective_stop_distance_pct": 0.0,
            "audit_trail": {
                "order_type": self.default_order_type,
                "spread_pct": 0.0,
                "impact_slippage_bps": 0.0,
                "failure_code": failure_code,
                "rejection_reason": reason,
            },
        }
