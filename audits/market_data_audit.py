"""
audits/market_data_audit.py

Performs comprehensive data integrity checks on market data series (OHLCV).
Catches price anomalies, missing candles, zero volumes, stale data sequences,
duplicates, future timestamps, and calculates an overall Data Quality Score.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Tuple

class MarketDataAudit:
    def __init__(self, df: pd.DataFrame, symbol: str, control_id: str = "CTRL_MARKET_DATA_INTEGRITY"):
        """
        Expected DataFrame columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        """
        self.df = df.copy()
        self.symbol = symbol
        self.control_id = control_id
        self.findings: List[Dict[str, Any]] = []

    def run_audit(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        self.findings = []
        
        if self.df.empty:
            self._add_finding(
                finding_id="MD_ERR_001",
                severity="CRITICAL",
                title="Empty Dataset",
                description=f"Market data dataset for {self.symbol} contains no records."
            )
            return self.findings, self._calculate_quality_score()

        self._normalize_timestamp_order()
        self._check_required_columns()
        self._check_duplicate_timestamps()
        self._check_future_timestamps()
        self._check_ohlc_consistency()
        self._check_negative_or_zero_prices()
        self._check_volume_anomalies()
        self._check_stale_data()
        self._check_missing_timestamps()
        self._check_price_spikes()

        return self.findings, self._calculate_quality_score()

    def _has_columns(self, columns: set) -> bool:
        return columns.issubset(self.df.columns)

    def _normalize_timestamp_order(self):
        if "timestamp" in self.df.columns:
            self.df["timestamp"] = pd.to_datetime(self.df["timestamp"], errors='coerce')
            self.df.sort_values("timestamp", inplace=True)
            self.df.reset_index(drop=True, inplace=True)

    def _add_finding(self, finding_id: str, severity: str, title: str, description: str, evidence: dict = None):
        self.findings.append({
            "finding_id": finding_id,
            "control_id": self.control_id,
            "severity": severity,
            "title": title,
            "description": description,
            "evidence": evidence or {"symbol": self.symbol, "total_records": len(self.df)},
            "detected_at": datetime.utcnow().isoformat()
        })

    def _check_required_columns(self):
        required = {'timestamp', 'open', 'high', 'low', 'close', 'volume'}
        missing = required - set(self.df.columns)
        if missing:
            self._add_finding(
                finding_id="MD_ERR_002",
                severity="CRITICAL",
                title="Missing Required Columns",
                description=f"Dataset for {self.symbol} is missing columns: {list(missing)}"
            )

    def _check_duplicate_timestamps(self):
        if "timestamp" not in self.df.columns:
            return
        duplicates = self.df['timestamp'].duplicated().sum()
        if duplicates > 0:
            self._add_finding(
                finding_id="MD_ERR_010",
                severity="HIGH",
                title="Duplicate Market Timestamps",
                description=f"Found {duplicates} duplicate timestamps for {self.symbol}."
            )

    def _check_future_timestamps(self):
        if "timestamp" not in self.df.columns:
            return
        now = datetime.utcnow()
        future = self.df[self.df['timestamp'] > now]
        if not future.empty:
            self._add_finding(
                finding_id="MD_ERR_011",
                severity="CRITICAL",
                title="Future Market Data Detected",
                description=f"{len(future)} candles have timestamps in the future."
            )

    def _check_ohlc_consistency(self):
        required = {"open", "high", "low", "close"}
        if not self._has_columns(required):
            return

        invalid_hl = self.df[self.df['high'] < self.df['low']]
        if not invalid_hl.empty:
            self._add_finding(
                finding_id="MD_ERR_003",
                severity="HIGH",
                title="OHLC Inconsistency: High < Low",
                description=f"Found {len(invalid_hl)} rows where High is lower than Low."
            )

        invalid_open = self.df[(self.df['open'] > self.df['high']) | (self.df['open'] < self.df['low'])]
        invalid_close = self.df[(self.df['close'] > self.df['high']) | (self.df['close'] < self.df['low'])]

        if not invalid_open.empty or not invalid_close.empty:
            self._add_finding(
                finding_id="MD_ERR_004",
                severity="HIGH",
                title="OHLC Inconsistency: Open/Close Out of Range",
                description=f"Found {len(invalid_open)} open and {len(invalid_close)} close prices outside High-Low bounds."
            )

    def _check_negative_or_zero_prices(self):
        required = {"open", "high", "low", "close"}
        if not self._has_columns(required):
            return

        invalid_prices = self.df[(self.df['open'] <= 0) | (self.df['high'] <= 0) | 
                                 (self.df['low'] <= 0) | (self.df['close'] <= 0)]
        if not invalid_prices.empty:
            self._add_finding(
                finding_id="MD_ERR_005",
                severity="CRITICAL",
                title="Zero or Negative Prices Detected",
                description=f"Found {len(invalid_prices)} rows with zero or negative price values."
            )

    def _check_volume_anomalies(self):
        if "volume" not in self.df.columns:
            return

        invalid_volume = self.df[self.df['volume'] < 0]
        if not invalid_volume.empty:
            self._add_finding(
                finding_id="MD_ERR_006",
                severity="HIGH",
                title="Negative Volume Detected",
                description=f"Found {len(invalid_volume)} rows with negative trading volume."
            )

        zero_volume = self.df[self.df['volume'] == 0]
        if len(zero_volume) > (len(self.df) * 0.05):
            self._add_finding(
                finding_id="MD_ERR_007",
                severity="MEDIUM",
                title="Excessive Zero-Volume Candles",
                description=f"{len(zero_volume)} candles have zero volume (>5% of dataset)."
            )

    def _check_stale_data(self):
        if "close" not in self.df.columns:
            return

        price_change = self.df['close'].diff()
        stale_mask = (price_change == 0)
        stale_runs = stale_mask.groupby((~stale_mask).cumsum()).sum()
        max_stale = stale_runs.max() if not stale_runs.empty else 0

        if max_stale > 10:
            self._add_finding(
                finding_id="MD_ERR_008",
                severity="MEDIUM",
                title="Stale Price Feed Detected",
                description=f"Detected a sequence of {max_stale} consecutive identical close prices."
            )

    def _check_missing_timestamps(self):
        if "timestamp" not in self.df.columns:
            return

        diffs = self.df['timestamp'].diff().dropna()
        if diffs.empty:
            return

        median_freq = diffs.median()
        gaps = diffs[diffs > (median_freq * 3)]
        if not gaps.empty:
            self._add_finding(
                finding_id="MD_ERR_009",
                severity="LOW",
                title="Irregular Time Gaps in Candles",
                description=f"Found {len(gaps)} significant time gaps larger than expected frequency."
            )

    def _check_price_spikes(self):
        if "close" not in self.df.columns:
            return

        returns = self.df['close'].pct_change().abs()
        spikes = returns[returns > 0.30]
        if not spikes.empty:
            self._add_finding(
                finding_id="MD_ERR_012",
                severity="HIGH",
                title="Extreme Price Movement Detected",
                description=f"Found {len(spikes)} candles with >30% price movement."
            )

    def _calculate_quality_score(self) -> Dict[str, Any]:
        score = 100
        penalties = {
            "CRITICAL": 35,
            "HIGH": 15,
            "MEDIUM": 5,
            "LOW": 2
        }

        for finding in self.findings:
            sev = finding.get("severity", "LOW")
            score -= penalties.get(sev, 2)

        score = max(0, score)
        
        status = "HEALTHY"
        if score < 50:
            status = "REJECTED"
        elif score < 80:
            status = "WARNING"

        return {
            "symbol": self.symbol,
            "quality_score": score,
            "status": status,
            "total_findings": len(self.findings)
        }
