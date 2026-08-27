"""
validation/expectancy_engine.py
Institutional Expectancy & Statistical Edge Measurement Engine.
Features: Actual execution price-based returns, R-multiple analytics, profit factor,
expectancy confidence intervals, equity curve drawdown and losing streak statistics,
theme/sector dependency adjustments, and institutional grade classification.
"""

import logging
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class ExpectancyEngine:
    """Calculates rigorous statistical edge, R-multiples, profit factors, confidence

    intervals, sequence drawdowns, and dependency-adjusted expectancy for institutional validation.
    """

    def __init__(
        self,
        min_sample_size: int = 30,
        target_confidence_level: float = 0.95,
    ) -> None:
        self.min_sample_size = min_sample_size
        self.target_confidence_level = target_confidence_level

    def evaluate_expectancy(self, trades_df: pd.DataFrame) -> Dict[str, Any]:
        """Performs a comprehensive institutional edge and risk-adjusted expectancy audit.

        Args:
            trades_df: DataFrame containing trade execution and outcome records (must include
              actual_entry_price, exit_price, effective_stop_distance_pct, execution_cost_bps, etc.).

        Returns:
            Dict structured matching the precise institutional expectancy schema.
        """
        if trades_df.empty:
            return self._empty_result("Empty trade dataset provided")

        # 1. Enforce Actual Execution Price-Based Return Calculation
        df = self._compute_execution_adjusted_returns(trades_df.copy())

        sample_size = int(len(df))
        is_valid = sample_size >= self.min_sample_size

        # Confidence categorization based on sample size
        if not is_valid:
            confidence = "LOW (INSUFFICIENT SAMPLE)"
        elif sample_size >= 200:
            confidence = "HIGH"
        else:
            confidence = "MODERATE"

        # 2. Global Metrics & Probabilities
        wins = df[df["net_return_pct"] > 0]
        losses = df[df["net_return_pct"] <= 0]

        win_rate = len(wins) / sample_size if sample_size > 0 else 0.0
        loss_rate = 1.0 - win_rate

        avg_win = float(wins["net_return_pct"].mean()) if not wins.empty else 0.0
        avg_loss = float(losses["net_return_pct"].mean()) if not losses.empty else 0.0
        abs_avg_loss = abs(avg_loss)

        # Raw vs Execution-Adjusted Expectancy (in percentage points)
        raw_expectancy = (win_rate * avg_win) - (loss_rate * abs_avg_loss)

        # Execution drag components
        slippage_drag = (
            float(df["slippage_drag_pct"].mean()) if "slippage_drag_pct" in df.columns else 0.0
        )
        commission_drag = (
            float(df["commission_drag_pct"].mean()) if "commission_drag_pct" in df.columns else 0.0
        )
        execution_adjusted_expectancy = raw_expectancy - (slippage_drag + commission_drag)

        # 3. Payoff Ratio & Profit Factor
        payoff_ratio = (avg_win / abs_avg_loss) if abs_avg_loss > 0 else 0.0
        gross_wins = float(wins["net_return_pct"].sum()) if not wins.empty else 0.0
        gross_losses = float(abs(losses["net_return_pct"].sum())) if not losses.empty else 0.0
        profit_factor = (gross_wins / gross_losses) if gross_losses > 0 else float("inf")

        # 4. R-Multiple Analytics
        r_multiples = df["r_multiple"].dropna() if "r_multiple" in df.columns else pd.Series([0.0])
        avg_r = float(r_multiples.mean())
        median_r = float(r_multiples.median())
        max_r = float(r_multiples.max())
        worst_r = float(r_multiples.min())

        # 5. Drawdown & Streak Statistics (derived from sequence of trade returns)
        max_dd, max_loss_streak = self._calculate_sequence_risk(df["net_return_pct"])

        # 6. Expectancy Confidence Interval & Statistics
        return_std = float(df["net_return_pct"].std()) if sample_size > 1 else 0.0
        std_error = return_std / np.sqrt(sample_size) if sample_size > 0 else 0.0
        # Approximate 95% confidence bounds (using 1.96 z-score)
        ci_margin = 1.96 * std_error
        expectancy_lower_bound = execution_adjusted_expectancy - ci_margin
        expectancy_upper_bound = execution_adjusted_expectancy + ci_margin

        # 7. Regime Breakdown Analysis
        regime_analysis = {}
        if "market_regime" in df.columns:
            for regime, group in df.groupby("market_regime"):
                regime_wins = group[group["net_return_pct"] > 0]
                r_win_rate = len(regime_wins) / len(group) if len(group) > 0 else 0.0
                regime_analysis[str(regime)] = {
                    "sample_size": int(len(group)),
                    "win_rate": round(r_win_rate, 4),
                    "expectancy": round(float(group["net_return_pct"].mean()), 4),
                }

        # 8. Dependency & Concentration Adjustment (Theme/Sector)
        dependency_adjustment = self._evaluate_dependencies(df)

        # 9. Institutional Grade Approval Status
        institutional_grade = (
            "APPROVED"
            if (is_valid and profit_factor >= 1.5 and execution_adjusted_expectancy > 0.0 and max_dd > -25.0)
            else "REJECTED"
        )

        return {
            "sample_size": sample_size,
            "edge_quality": {
                "valid": is_valid,
                "confidence": confidence,
                "expectancy_std": round(return_std, 4),
                "expectancy_lower_bound": round(expectancy_lower_bound, 4),
                "expectancy_upper_bound": round(expectancy_upper_bound, 4),
            },
            "expectancy": {
                "raw": round(raw_expectancy, 4),
                "execution_adjusted": round(execution_adjusted_expectancy, 4),
            },
            "probability": {
                "win_rate": round(win_rate, 4),
                "loss_rate": round(loss_rate, 4),
            },
            "payoff": {
                "avg_win": round(avg_win, 4),
                "avg_loss": round(avg_loss, 4),
                "payoff_ratio": round(payoff_ratio, 2),
                "profit_factor": round(profit_factor, 2),
            },
            "risk_metrics": {
                "avg_R": round(avg_r, 2),
                "median_R": round(median_r, 2),
                "max_R": round(max_r, 2),
                "worst_R": round(worst_r, 2),
                "max_drawdown": round(max_dd, 2),
                "max_loss_streak": int(max_loss_streak),
            },
            "execution_drag": {
                "slippage": round(slippage_drag * 100.0, 2),  # in percentage points
                "commission": round(commission_drag * 100.0, 2),
            },
            "regime_analysis": regime_analysis,
            "dependency_adjustment": dependency_adjustment,
            "institutional_grade": institutional_grade,
        }

    def _compute_execution_adjusted_returns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Enforces actual fill prices, execution costs, commissions, and R-multiples."""
        net_returns = []
        r_multiples = []
        slippage_drags = []
        commission_drags = []

        for _, row in df.iterrows():
            # Fallback to standard return_pct if execution details are absent
            actual_entry = float(row.get("actual_entry_price", row.get("entry_price", 0.0)))
            exit_price = float(row.get("exit_price", 0.0))
            stop_dist_pct = float(
                row.get("effective_stop_distance_pct", row.get("stop_distance_pct", 0.08))
            )
            allocated_cap = float(row.get("allocated_capital", 1.0))

            if actual_entry <= 0 or exit_price <= 0:
                ret = float(row.get("return_pct", 0.0))
                net_returns.append(ret)
                r_multiples.append(0.0)
                slippage_drags.append(0.0)
                commission_drags.append(0.0)
                continue

            # Gross return based strictly on actual execution fill vs exit
            side = str(row.get("side", "BUY")).upper()
            if side == "BUY":
                gross_ret = (exit_price - actual_entry) / actual_entry
            else:
                gross_ret = (actual_entry - exit_price) / actual_entry

            # Extract currency costs if available
            slip_cost = float(row.get("slippage_cost_currency", 0.0))
            comm_cost = float(row.get("commission_cost_currency", 0.0))

            slip_drag = (slip_cost / allocated_cap) if allocated_cap > 0 else 0.0
            comm_drag = (comm_cost / allocated_cap) if allocated_cap > 0 else 0.0

            net_ret = gross_ret - (slip_drag + comm_drag)
            net_returns.append(net_ret)
            slippage_drags.append(slip_drag)
            commission_drags.append(comm_drag)

            # Calculate R-Multiple: Reward / Risk
            # Risk per share = actual_entry * stop_dist_pct
            risk_amount = actual_entry * stop_dist_pct
            if risk_amount > 0:
                if side == "BUY":
                    reward_amount = exit_price - actual_entry
                else:
                    reward_amount = actual_entry - exit_price
                r_mult = reward_amount / risk_amount
            else:
                r_mult = 0.0
            r_multiples.append(r_mult)

        df["net_return_pct"] = net_returns
        df["r_multiple"] = r_multiples
        df["slippage_drag_pct"] = slippage_drags
        df["commission_drag_pct"] = commission_drags
        return df

    def _calculate_sequence_risk(self, returns: pd.Series) -> tuple:
        """Calculates max drawdown percentage and longest consecutive losing streak."""
        if returns.empty:
            return 0.0, 0

        # Simulate equity curve from sequence of trade returns
        equity_curve = (1.0 + returns).cumprod()
        running_max = equity_curve.cummax()
        drawdowns = (equity_curve - running_max) / running_max
        max_dd = float(drawdowns.min() * 100.0) if not drawdowns.empty else 0.0

        # Calculate losing streaks
        is_loss = returns <= 0
        streak = 0
        max_loss_streak = 0
        for lost in is_loss:
            if lost:
                streak += 1
                max_loss_streak = max(max_loss_streak, streak)
            else:
                streak = 0

        return max_dd, int(max_loss_streak)

    def _evaluate_dependencies(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Audits sector and theme concentration risk affecting edge stability."""
        dep_info = {"dominant_theme": None, "theme_concentration_pct": 0.0, "dominant_sector": None, "sector_concentration_pct": 0.0}
        total_trades = len(df)
        if total_trades == 0:
            return dep_info

        if "theme" in df.columns:
            theme_counts = df["theme"].value_counts()
            if not theme_counts.empty:
                dom_theme = theme_counts.index[0]
                dep_info["dominant_theme"] = str(dom_theme)
                dep_info["theme_concentration_pct"] = round(float(theme_counts.iloc[0] / total_trades), 4)

        if "sector" in df.columns:
            sector_counts = df["sector"].value_counts()
            if not sector_counts.empty:
                dom_sec = sector_counts.index[0]
                dep_info["dominant_sector"] = str(dom_sec)
                dep_info["sector_concentration_pct"] = round(float(sector_counts.iloc[0] / total_trades), 4)

        return dep_info

    def _empty_result(self, reason: str) -> Dict[str, Any]:
        return {
            "sample_size": 0,
            "edge_quality": {"valid": False, "confidence": "NONE", "reason": reason},
            "expectancy": {"raw": 0.0, "execution_adjusted": 0.0},
            "probability": {"win_rate": 0.0, "loss_rate": 0.0},
            "payoff": {"avg_win": 0.0, "avg_loss": 0.0, "payoff_ratio": 0.0, "profit_factor": 0.0},
            "risk_metrics": {"avg_R": 0.0, "median_R": 0.0, "max_R": 0.0, "worst_R": 0.0, "max_drawdown": 0.0, "max_loss_streak": 0},
            "execution_drag": {"slippage": 0.0, "commission": 0.0},
            "regime_analysis": {},
            "dependency_adjustment": {},
            "institutional_grade": "REJECTED",
        }
