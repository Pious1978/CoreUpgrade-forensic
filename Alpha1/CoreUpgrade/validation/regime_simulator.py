"""
validation/regime_simulator.py
Institutional Market Regime Stress-Testing Engine (Upgraded)

Consumes feature-engineered market regimes to simulate strategy resilience, 
tail drawdowns, recovery timelines, and survival probabilities across 
macro environments (Bull, Bear, Sideways, High Volatility, Crisis).
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional


class RegimeSimulator:
    def __init__(
        self, 
        trades: List[Dict[str, Any]], 
        regime_allocations: Optional[Dict[str, float]] = None,
        max_drawdown_limit_pct: float = 25.0,
        simulation_count: int = 1000
    ):
        """
        Initializes the upgraded regime stress-testing engine.

        Args:
            trades: List of trade records enriched with 'market_regime' tags.
            regime_allocations: Target exposure probabilities across market environments.
            max_drawdown_limit_pct: Maximum allowable drawdown threshold for institutional survival.
            simulation_count: Number of Monte Carlo paths to execute per regime.
        """
        self.trades = trades
        self.regime_allocations = regime_allocations or {
            "bull": 0.35,
            "bear": 0.25,
            "sideways": 0.20,
            "high_vol": 0.15,
            "crisis": 0.05
        }
        self.max_dd_limit = max_drawdown_limit_pct
        self.simulation_count = simulation_count

    def _segment_trades_by_regime(self) -> Dict[str, List[Dict[str, Any]]]:
        """Segments trades into distinct macro environment pools."""
        pools = {regime: [] for regime in self.regime_allocations.keys()}
        
        for trade in self.trades:
            regime = trade.get("market_regime", "bull").lower()
            if regime in pools:
                pools[regime].append(trade)
            else:
                pools.setdefault("bull", []).append(trade)

        # Fallback for empty regime pools to maintain simulation continuity
        default_pool = self.trades if self.trades else [{"net_return": 0.0, "r_multiple": 0.0}]
        for regime in pools:
            if not pools[regime]:
                pools[regime] = default_pool
                
        return pools

    def simulate_regimes(self) -> Dict[str, Any]:
        """
        Executes regime-specific stress testing across survival metrics.

        Returns:
            Dictionary matching the institutional regime survival report contract.
        """
        rng = np.random.default_rng(seed=42)
        regime_pools = self._segment_trades_by_regime()
        regime_survival_results = {}

        for regime_name, allocation_weight in self.regime_allocations.items():
            pool = regime_pools.get(regime_name, self.trades)
            path_returns = []
            path_drawdowns = []
            recovery_months_list = []
            surviving_runs = 0

            # Simulate path sequences for the specific regime environment
            for _ in range(self.simulation_count):
                # Sample a sub-sequence representing a regime cycle (e.g., 20 trades horizon)
                sample_size = min(len(pool), 20)
                sampled_trades = rng.choice(pool, size=sample_size, replace=True)

                # Track equity curve for drawdowns and recovery
                equity = 100.0
                peak = 100.0
                max_dd = 0.0
                underwater_periods = 0
                max_underwater = 0

                for t in sampled_trades:
                    ret = t.get("net_return", 0.0)
                    equity *= (1.0 + ret)

                    if equity > peak:
                        peak = equity
                        underwater_periods = 0
                    else:
                        underwater_periods += 1
                        if underwater_periods > max_underwater:
                            max_underwater = underwater_periods

                    dd = ((peak - equity) / peak) * 100.0
                    if dd > max_dd:
                        max_dd = dd

                total_return = ((equity - 100.0) / 100.0) * 100.0
                
                path_returns.append(total_return)
                path_drawdowns.append(max_dd)
                
                # Estimate recovery duration in months (assuming ~3 trades per month pace)
                recovery_months = max(1, int(max_underwater / 3))
                recovery_months_list.append(recovery_months)

                # Institutional survival criteria: Max DD within limits and positive/controlled return
                if max_dd <= self.max_dd_limit and total_return > -15.0:
                    surviving_runs += 1

            # Aggregate statistics for the regime
            survival_probability = round((surviving_runs / self.simulation_count) * 100.0, 1)
            median_return = round(float(np.median(path_returns)), 1)
            median_drawdown = round(float(np.median(path_drawdowns)), 1)
            max_recovery_months = int(np.percentile(recovery_months_list, 90)) # 90th percentile tail recovery time

            regime_survival_results[regime_name] = {
                "survival_probability": survival_probability,
                "median_return": median_return,
                "median_drawdown": median_drawdown,
                "max_recovery_months": max_recovery_months
            }

        return {
            "regime_allocations_tested": self.regime_allocations,
            "max_drawdown_limit_pct": self.max_dd_limit,
            "regime_survival": regime_survival_results
        }
