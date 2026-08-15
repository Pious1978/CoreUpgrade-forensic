#!/usr/bin/env python3
"""
audits/market_data/missing_history.py
Performs institutional missing history and data completeness audits with fully upgraded 
repair queue schema metadata, execution runtime baselines, and safe attribute fallbacks.
"""

import datetime
import statistics
import logging
import bisect
import json
import pathlib
from collections import defaultdict
from audits.database.base import BaseAudit, register_audit
from core.market_calendar import MarketCalendar
from audits.market_data.config import MARKET_AUDIT_CONFIG

logger = logging.getLogger("DatabaseAudit")

@register_audit(level=2)
class MissingHistoryAudit(BaseAudit):
    def run(self):
        audit_start = datetime.datetime.now()
        db_name = getattr(self, "db_name", getattr(self, "database_path", "market_data.db"))
        
        cursor = self.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='prices';")
        if not cursor.fetchone():
            self.log("Data Quality", "FAIL", "Missing History", "Prices table missing from market data database.")
            return

        cursor.execute("SELECT MIN(Date), MAX(Date) FROM prices;")
        min_date_str, max_date_str = cursor.fetchone()
        if not min_date_str or not max_date_str:
            self.log("Data Quality", "WARNING", "Missing History", "Prices table contains no date records.")
            return

        global_start = datetime.datetime.strptime(min_date_str, "%Y-%m-%d").date()
        global_end = datetime.datetime.strptime(max_date_str, "%Y-%m-%d").date()

        # Cache master trading days as sorted datetime.date objects
        master_trading_days = []
        curr = global_start
        while curr <= global_end:
            if MarketCalendar.is_session(curr):
                master_trading_days.append(curr)
            curr += datetime.timedelta(days=1)

        cursor.execute("SELECT Symbol, Date FROM prices ORDER BY Symbol, Date;")
        rows = cursor.fetchall()
        records_scanned = len(rows)

        symbol_dates = defaultdict(set)
        symbol_bounds = {}
        invalid_date_count = 0

        for symbol, date_str in rows:
            try:
                d_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                invalid_date_count += 1
                continue
            
            symbol_dates[symbol].add(d_obj)
            if symbol not in symbol_bounds:
                symbol_bounds[symbol] = {"min": d_obj, "max": d_obj}
            else:
                if d_obj < symbol_bounds[symbol]["min"]:
                    symbol_bounds[symbol]["min"] = d_obj
                if d_obj > symbol_bounds[symbol]["max"]:
                    symbol_bounds[symbol]["max"] = d_obj

        if invalid_date_count > 0:
            self.log("Data Quality", "FAIL", "Date Format Validation", f"Encountered {invalid_date_count:,} malformed/invalid date entries in prices table.")
        else:
            self.log("Data Quality", "PASS", "Date Format Validation", "No malformed date entries detected in prices table scan.")

        symbols = list(symbol_bounds.keys())
        symbols_scanned = len(symbols)

        complete_count = 0
        tolerance_count = 0
        warning_count = 0
        fail_count = 0
        critical_count = 0
        largest_gap = 0
        coverages = []
        repair_symbol_map = {}

        tolerance = MARKET_AUDIT_CONFIG["thresholds"].get("missing_session_tolerance", 5)
        pass_threshold_pct = MARKET_AUDIT_CONFIG["thresholds"].get("coverage_pass_pct", 99.5)
        warn_threshold_pct = MARKET_AUDIT_CONFIG["thresholds"].get("coverage_warning_pct", 95.0)

        for idx, symbol in enumerate(symbols, 1):
            if symbols_scanned >= 500 and idx % 500 == 0:
                logger.info(f"Progress: Audited {idx}/{symbols_scanned} symbols for missing history...")

            sym_min = symbol_bounds[symbol]["min"]
            sym_max = symbol_bounds[symbol]["max"]

            left_idx = bisect.bisect_left(master_trading_days, sym_min)
            right_idx = bisect.bisect_right(master_trading_days, sym_max)
            expected_dates = set(master_trading_days[left_idx:right_idx])
            actual_dates = symbol_dates[symbol]

            missing_date_objs = sorted(list(expected_dates - actual_dates))
            missing_dates_str = [d.strftime("%Y-%m-%d") for d in missing_date_objs]
            gap_size = len(missing_dates_str)

            if gap_size > largest_gap:
                largest_gap = gap_size

            expected_count = len(expected_dates)
            actual_count = len(actual_dates)
            coverage = (actual_count / expected_count * 100) if expected_count > 0 else 100.0
            coverages.append(coverage)

            # Determine Symbol-level Status & Severity Mapping
            if gap_size == 0 and coverage >= pass_threshold_pct:
                complete_count += 1
                sym_status = "COMPLETE"
            elif gap_size <= tolerance and coverage >= warn_threshold_pct:
                tolerance_count += 1
                sym_status = "WITHIN_TOLERANCE"
            elif coverage >= warn_threshold_pct and gap_size <= 20:
                warning_count += 1
                sym_status = "WARNING"
                self.log("Data Quality", "WARNING", "Missing History", f"Symbol '{symbol}' has {gap_size} missing sessions (Coverage: {coverage:.2f}%).")
            elif coverage >= 80.0:
                fail_count += 1
                sym_status = "FAIL"
                self.log("Data Quality", "FAIL", "Missing History", f"Symbol '{symbol}' has {gap_size} missing sessions (Coverage: {coverage:.2f}%).")
            else:
                critical_count += 1
                sym_status = "CRITICAL"
                self.log("Data Quality", "CRITICAL", "Missing History", f"Symbol '{symbol}' has severe coverage drop ({coverage:.2f}%).")

            if gap_size > 0:
                repair_symbol_map[symbol] = {
                    "missing_sessions": missing_dates_str,
                    "missing_count": gap_size,
                    "coverage_pct": round(coverage, 2),
                    "status": sym_status
                }

        audit_end = datetime.datetime.now()
        duration_seconds = round((audit_end - audit_start).total_seconds(), 2)

        # Persist fully upgraded metadata-rich repair queue artifact
        repair_file_path = MARKET_AUDIT_CONFIG["outputs"]["repair_queue_file"]
        try:
            pathlib.Path(repair_file_path).parent.mkdir(parents=True, exist_ok=True)
            repair_payload = {
                "database": str(db_name),
                "generated": audit_end.isoformat(),
                "audit": "missing_history",
                "duration_seconds": duration_seconds,
                "records_scanned": records_scanned,
                "symbols_scanned": symbols_scanned,
                "symbols": repair_symbol_map
            }
            with open(repair_file_path, "w", encoding="utf-8") as f:
                json.dump(repair_payload, f, indent=4)
        except Exception as e:
            logger.warning(f"Could not persist repair queue artifact to {repair_file_path}: {e}")

        # Advanced Distribution Metrics
        if coverages:
            coverages.sort()
            avg_coverage = statistics.mean(coverages)
            median_coverage = statistics.median(coverages)
            worst_coverage = coverages[0]
        else:
            avg_coverage = median_coverage = worst_coverage = 100.0

        # Refined Summary Severity Logic
        if critical_count > 0:
            summary_severity = "CRITICAL"
        elif invalid_date_count > 0:
            summary_severity = "FAIL"
        elif fail_count > 0:
            summary_severity = "FAIL"
        elif warning_count > 0:
            summary_severity = "WARNING"
        else:
            summary_severity = "PASS"

        summary_msg = (
            f"\n========================================\n"
            f"          Missing History Summary       \n"
            f"========================================\n"
            f"Database                 : {db_name}\n"
            f"Runtime                  : {duration_seconds}s\n"
            f"Records Scanned          : {records_scanned:,}\n"
            f"Symbols Audited          : {symbols_scanned:,}\n"
            f"Complete (0 gaps)        : {complete_count:,}\n"
            f"Within Tolerance (<= {tolerance}): {tolerance_count:,}\n"
            f"Warnings                 : {warning_count:,}\n"
            f"Failures                 : {fail_count:,}\n"
            f"Critical                 : {critical_count:,}\n"
            f"Malformed Dates Found    : {invalid_date_count:,}\n"
            f"Largest Missing Gap      : {largest_gap} sessions\n"
            f"Average Coverage         : {avg_coverage:.2f}%\n"
            f"Median Coverage          : {median_coverage:.2f}%\n"
            f"Worst Coverage           : {worst_coverage:.2f}%\n"
            f"Repair Queue Artifact    : {repair_file_path} ({len(repair_symbol_map):,} symbols)\n"
            f"========================================"
        )
        
        self.log("Data Quality", summary_severity, "Missing History Summary", summary_msg, exec_time=duration_seconds * 1000)
