#!/usr/bin/env python3
"""
audits/market_data/corporate_actions.py
Detects unadjusted stock splits, bonus issues, and massive overnight price discontinuities 
that indicate missing corporate action adjustments.
"""

import sqlite3
from audits.database.base import BaseAudit, register_audit
from audits.market_data.config import MARKET_AUDIT_CONFIG

@register_audit(level=2)
class CorporateActionsAudit(BaseAudit):
    def run(self):
        cursor = self.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='prices';")
        if not cursor.fetchone():
            return

        threshold_pct = MARKET_AUDIT_CONFIG["thresholds"].get("split_detection_threshold_pct", 40.0)

        # SQL Window function to detect massive overnight price jumps or drops (indicative of unadjusted stock splits)
        cursor.execute("""
            WITH lagged AS (
                SELECT Symbol, Date, Close, 
                       LAG(Close, 1) OVER (PARTITION BY Symbol ORDER BY Date ASC) as prev_close
                FROM prices
            )
            SELECT Symbol, Date, prev_close, Close, 
                   ((Close - prev_close) / prev_close * 100.0) as return_pct
            FROM lagged
            WHERE prev_close IS NOT NULL 
              AND ABS((Close - prev_close) / prev_close * 100.0) >= ?
            ORDER BY ABS(return_pct) DESC
            LIMIT 25;
        """, (threshold_pct,))

        discontinuities = cursor.fetchall()
        if discontinuities:
            self.log("Data Quality", "WARNING", "Corporate Actions", f"Detected {len(discontinuities)} extreme overnight price discontinuities (>= {threshold_pct}%) which may indicate unadjusted stock splits or corporate actions.")
            for sym, date, p_close, close, ret in discontinuities:
                self.log("Data Quality", "WARNING", "Corporate Actions", f"Symbol '{sym}' on {date}: Prev Close {p_close}, Current Close {close} (Change: {ret:+.1f}%)")
        else:
            self.log("Data Quality", "PASS", "Corporate Actions", "No extreme unadjusted overnight price discontinuities detected.")
