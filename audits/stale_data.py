import datetime
from audits.database.base import BaseAudit
from core.config import get_config
from core.market_calendar import MarketCalendar

class StaleDataAudit(BaseAudit):
    def __init__(self, context):
        super().__init__(context)
        self.thresholds = get_config("stale_data") or {
            "warning_sessions": 1,
            "fail_sessions": 2,
            "critical_sessions": 5,
            "critical_symbol_pct_threshold": 0.5,
            "invalid_warning_pct": 1.0,
            "invalid_critical_pct": 5.0,
            "audit_version": "1.0",
            "max_stale_symbol_reports": 50
        }
        self.audit_version = self.thresholds.get("audit_version", "1.0")

    def run(self, db_name: str, symbols_data: list, db_latest_date: datetime.date):
        start_time = datetime.datetime.now()
        expected_latest_session = self.context.audit_date

        try:
            warning_threshold = self.thresholds.get("warning_sessions", 1)
            fail_threshold = self.thresholds.get("fail_sessions", 2)
            critical_threshold = self.thresholds.get("critical_sessions", 5)
            critical_symbol_pct_threshold = self.thresholds.get("critical_symbol_pct_threshold", 0.5)
            invalid_warning_pct = self.thresholds.get("invalid_warning_pct", 1.0)
            invalid_critical_pct = self.thresholds.get("invalid_critical_pct", 5.0)
            MAX_STALE_SYMBOL_REPORTS = self.thresholds.get("max_stale_symbol_reports", 50)

            total_audited = 0
            fresh_symbols = 0
            warning_stale = 0
            fail_stale = 0
            critical_stale = 0
            invalid_records_count = 0

            max_symbol_lag = 0
            most_stale_symbol = None
            stale_symbols = []

            for record in symbols_data:
                total_audited += 1
                symbol = record.get("symbol", "UNKNOWN")
                
                if "latest_date" not in record:
                    invalid_records_count += 1
                    continue

                try:
                    sym_latest_date = datetime.datetime.strptime(record["latest_date"], "%Y-%m-%d").date()
                except (ValueError, TypeError, KeyError):
                    invalid_records_count += 1
                    continue

                sym_lag = MarketCalendar.session_lag(sym_latest_date, db_latest_date)

                if sym_lag > 0:
                    if len(stale_symbols) < MAX_STALE_SYMBOL_REPORTS:
                        stale_symbols.append({
                            "symbol": symbol,
                            "lag": sym_lag
                        })
                    if sym_lag > max_symbol_lag:
                        max_symbol_lag = sym_lag
                        most_stale_symbol = symbol

                if sym_lag == 0:
                    fresh_symbols += 1
                elif sym_lag <= warning_threshold:
                    warning_stale += 1
                elif sym_lag <= fail_threshold:
                    fail_stale += 1
                else:
                    critical_stale += 1

            valid_records = total_audited - invalid_records_count
            global_lag_sessions = MarketCalendar.session_lag(db_latest_date, expected_latest_session)

            total_stale = warning_stale + fail_stale + critical_stale
            stale_percentage = (total_stale / valid_records * 100) if valid_records > 0 else 0.0
            critical_symbol_pct = (critical_stale / valid_records * 100) if valid_records > 0 else 0.0
            invalid_percentage = (invalid_records_count / total_audited * 100) if total_audited > 0 else 0.0

            freshness_score = (
                fresh_symbols * 100
                + warning_stale * 90
                + fail_stale * 50
                + critical_stale * 0
            ) / valid_records if valid_records > 0 else 100.0

            stale_symbols = sorted(
                stale_symbols,
                key=lambda x: x["lag"],
                reverse=True
            )

            is_critical_pct_breached = critical_symbol_pct >= critical_symbol_pct_threshold if valid_records > 0 else False

            if (critical_stale > 0 and is_critical_pct_breached) or global_lag_sessions >= critical_threshold or invalid_percentage >= invalid_critical_pct:
                global_severity = "CRITICAL"
            elif fail_stale > 0 or critical_stale > 0 or invalid_percentage >= invalid_warning_pct:
                global_severity = "FAIL"
            elif warning_stale > 0 or global_lag_sessions > 0 or invalid_percentage > 0.0:
                global_severity = "WARNING"
            else:
                global_severity = "PASS"

            execution_time_ms = (datetime.datetime.now() - start_time).total_seconds() * 1000

            self.context.add_result(
                {
                    "audit_name": "stale_data",
                    "execution": {
                        "run_id": self.context.run_id,
                        "timestamp": self.context.timestamp,
                        "duration_ms": round(execution_time_ms, 2),
                        "audit_version": self.audit_version
                    },
                    "classification": {
                        "category": "market_data",
                        "severity": global_severity,
                        "execution_status": "SUCCESS"
                    },
                    "metrics": {
                        "freshness": {
                            "score": round(freshness_score, 2),
                            "expected_session": str(expected_latest_session),
                            "latest_session": str(db_latest_date),
                            "lag_sessions": global_lag_sessions
                        },
                        "symbols": {
                            "total": total_audited,
                            "valid": valid_records,
                            "fresh": fresh_symbols,
                            "warning": warning_stale,
                            "fail": fail_stale,
                            "critical": critical_stale,
                            "stale_percentage": round(stale_percentage, 2),
                            "most_stale_symbol": most_stale_symbol,
                            "most_stale_symbol_lag": max_symbol_lag,
                            "stale_symbol_examples": stale_symbols[:20]
                        },
                        "data_quality": {
                            "malformed_records": invalid_records_count,
                            "malformed_percentage": round(invalid_percentage, 2)
                        }
                    }
                }
            )

        except Exception as e:
            execution_time_ms = (datetime.datetime.now() - start_time).total_seconds() * 1000
            self.context.add_result(
                {
                    "audit_name": "stale_data",
                    "execution": {
                        "run_id": self.context.run_id,
                        "timestamp": self.context.timestamp,
                        "duration_ms": round(execution_time_ms, 2),
                        "audit_version": self.audit_version
                    },
                    "classification": {
                        "category": "market_data",
                        "severity": "CRITICAL",
                        "execution_status": "FAILED"
                    },
                    "error": {
                        "type": type(e).__name__,
                        "message": str(e)
                    }
                }
            )
