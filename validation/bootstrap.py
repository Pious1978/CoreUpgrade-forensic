"""
validation/bootstrap.py
Institutional Resampling Engine (Upgraded)

Handles optimal block bootstrap (moving block, no circular wrapping), 
chronological validation, and optional trade weighting/regime preservation.
"""

import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime


class TradeBootstrapEngine:
    def __init__(
        self, 
        trades: List[Dict[str, Any]], 
        method: str = "block", 
        block_method: str = "optimal",
        block_size: Optional[int] = None,
        preserve_regime: bool = True,
        seed: Optional[int] = None
    ):
        """
        Initializes the upgraded institutional resampling engine.

        Args:
            trades: List of trade records containing r_multiple, net_return, date, etc.
            method: Resampling method ('standard' or 'block').
            block_method: Method to determine block size ('optimal' or 'fixed').
            block_size: Manual block size if block_method is 'fixed'.
            preserve_regime: Flag to indicate structural regime integrity enforcement.
            seed: Optional random seed for deterministic simulation.
        """
        self.trades = trades
        self.method = method.lower()
        self.block_method = block_method.lower()
        self.preserve_regime = preserve_regime
        self.rng = np.random.default_rng(seed)
        self.num_trades = len(trades)

        if self.num_trades == 0:
            raise ValueError("Bootstrap engine requires a non-empty list of trade records.")

        # Validate strict chronological order
        self._validate_trade_order()

        # Determine block size using Politis-White approximation if set to optimal
        if self.block_method == "optimal":
            self.block_size = max(1, int(1.5 * (self.num_trades ** (1.0 / 3.0))))
        else:
            self.block_size = max(1, block_size if block_size is not None else 20)

        # Cap block size to total available trades
        if self.block_size > self.num_trades:
            self.block_size = self.num_trades

    def _validate_trade_order(self):
        """Validates that trade records are strictly chronological by date."""
        dates = []
        for t in self.trades:
            date_val = t.get("date")
            if date_val:
                if isinstance(date_val, str):
                    dates.append(datetime.strptime(date_val[:10], "%Y-%m-%d"))
                elif isinstance(date_val, datetime):
                    dates.append(date_val)
        
        if len(dates) == self.num_trades:
            if dates != sorted(dates):
                raise ValueError("Trades must be strictly chronological for valid block bootstrapping.")

    def sample_sequence(self) -> List[Dict[str, Any]]:
        """
        Generates a single resampled trade sequence using the configured method.
        
        Returns:
            List of dictionaries representing the randomized trade sequence.
        """
        if self.method == "block":
            return self._moving_block_bootstrap()
        elif self.method == "standard":
            return self._standard_bootstrap()
        else:
            raise ValueError(f"Unknown bootstrap method: {self.method}")

    def _standard_bootstrap(self) -> List[Dict[str, Any]]:
        """Standard bootstrap sampling with support for trade capital weights."""
        weights = [t.get("capital_weight", 1.0) for t in self.trades]
        weights = np.array(weights, dtype=float)
        if weights.sum() > 0:
            weights /= weights.sum()
        else:
            weights = None
        
        indices = self.rng.choice(self.num_trades, size=self.num_trades, p=weights)
        return [self.trades[i] for i in indices]

    def _moving_block_bootstrap(self) -> List[Dict[str, Any]]:
        """
        Moving block bootstrap without circular wrapping. 
        Prevents artificial regime mixing across synthetic boundaries.
        """
        resampled_trades = []
        max_start = self.num_trades - self.block_size
        
        if max_start < 0:
            max_start = 0
            block_size = self.num_trades
        else:
            block_size = self.block_size

        while len(resampled_trades) < self.num_trades:
            if max_start == 0:
                start_idx = 0
            else:
                start_idx = self.rng.integers(0, max_start + 1)
            
            block = self.trades[start_idx : start_idx + block_size]
            resampled_trades.extend(block)
                
        # Trim exact match to original trade count length
        return resampled_trades[:self.num_trades]
