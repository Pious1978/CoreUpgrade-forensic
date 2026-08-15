import numpy as np
import pandas as pd
from typing import List, Dict, Any

class MonteCarloEngine:
    """
    Block-bootstrap Monte Carlo engine preserving market regimes and volatility clustering.
    """
    
    def __init__(self, trades: List[Dict[str, Any]], initial_capital: float = 1_000_000, num_simulations: int = 1000, block_size: int = 10):
        self.trades = trades
        self.initial_capital = initial_capital
        self.num_simulations = num_simulations
        self.block_size = block_size
        
        self.weighted_returns = np.array([
            t.get("return_pct", 0.01) * t.get("capital_weight", 1.0) 
            for t in trades
        ])
        
        self.holding_years = 1.0
        if trades and "entry_date" in trades[0] and "exit_date" in trades[-1]:
            try:
                d_start = pd.to_datetime(trades[0]["entry_date"])
                d_end = pd.to_datetime(trades[-1]["exit_date"])
                days = (d_end - d_start).days
                if days > 0:
                    self.holding_years = days / 365.25
            except Exception:
                pass

    def run_simulation(self) -> Dict[str, Any]:
        n = len(self.weighted_returns)
        if n == 0:
            return {"error": "No trades provided for Monte Carlo simulation."}
            
        simulated_cagrs = []
        simulated_max_dds = []
        
        # Create blocks for block bootstrap
        b_size = max(1, min(self.block_size, n))
        blocks = [self.weighted_returns[i:i + b_size] for i in range(0, n, b_size)]
        n_blocks = len(blocks)
        
        for _ in range(self.num_simulations):
            # Sample blocks with replacement to preserve regime volatility clusters
            chosen_indices = np.random.choice(n_blocks, size=n_blocks, replace=True)
            sampled_returns = np.concatenate([blocks[idx] for idx in chosen_indices])
            
            equity = self.initial_capital * np.cumprod(1 + sampled_returns)
            equity_series = np.insert(equity, 0, self.initial_capital)
            
            total_return = equity[-1] / self.initial_capital
            years = max(self.holding_years, 0.5)
            cagr = (total_return ** (1 / years)) - 1.0
            simulated_cagrs.append(cagr * 100)
            
            peak = np.maximum.accumulate(equity_series)
            dd = (equity_series - peak) / peak
            simulated_max_dds.append(dd.min() * 100)
            
        return {
            "simulations_run": self.num_simulations,
            "method": "block_bootstrap_regime",
            "block_size": b_size,
            "cagr_percentiles": {
                "5th": round(np.percentile(simulated_cagrs, 5), 2),
                "25th": round(np.percentile(simulated_cagrs, 25), 2),
                "median": round(np.percentile(simulated_cagrs, 50), 2),
                "75th": round(np.percentile(simulated_cagrs, 75), 2),
                "95th": round(np.percentile(simulated_cagrs, 95), 2),
            },
            "max_dd_percentiles": {
                "5th_worst": round(np.percentile(simulated_max_dds, 5), 2),
                "median": round(np.percentile(simulated_max_dds, 50), 2),
                "95th_best": round(np.percentile(simulated_max_dds, 95), 2),
            }
        }
