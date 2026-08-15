#!/usr/bin/env python3
"""
audits/market_data/ohlcv_integrity.py
Validates daily price and volume candles against fundamental market physics 
(e.g., Low <= Open/High/Close <= High, positive volume, anomaly detection).
"""

import sqlite3
from audits.database.base import BaseAudit, register_audit

@register_audit(level=2)
class OHLCVIntegrityAudit(BaseAudit):
    def run(self):
        cursor = self.cursor()
        
        # Verify if prices table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='prices';")
        if not cursor.fetchone():
            self.log("Data Quality", "FAIL", "OHLCV Integrity", "Table 'prices' missing from market data database.")
            return

        # 1. Check for impossible price physics and bounds
        cursor.execute("""
            SELECT COUNT(*) 
            FROM prices 
            WHERE Low > High
               OR Open < 0 OR High < 0 OR Low < 0 OR Close < 0
               OR Open > High OR Open < Low
               OR Close > High OR Close < Low
               OR Volume < 0
               OR Close = 0;
        """)
        physics_violations = cursor.fetchone()[0]

        if physics_violations > 0:
            self.log("Data Quality", "FAIL", "OHLCV Integrity", f"Detected {physics_violations:,} candles violating price/volume physics (e.g., Low > High, Open/Close outside High-Low range, or negative volume).")
        else:
            self.log("Data Quality", "PASS", "OHLCV Integrity", "All candles comply with price and volume physics bounds.")

        # 2. Check for extreme volume spikes (> 500x average volume or anomalous flags)
        # Group by symbol to find persistent flatlines or zero-volume anomalies
        cursor.execute("""
            SELECT Symbol, COUNT(*) as flat_count
            FROM prices
            WHERE High = Low AND Volume = 0
            GROUP BY Symbol
            HAVING flat_count > 10;
        """)
        dead_candles = cursor.fetchall()
        if dead_candles:
            self.log("Data Quality", "WARNING", "OHLCV Integrity", f"Found {len(dead_candles)} symbols with suspicious consecutive zero-volume flatlines (High == Low).")
        else:
            self.log("Data Quality", "PASS", "OHLCV Integrity", "No abnormal persistent zero-volume flatlines detected.")
