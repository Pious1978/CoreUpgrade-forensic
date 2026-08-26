"""
core/config.py

Institutional Market Data Audit Configuration
Central configuration registry for all audit modules.
"""

from pathlib import Path


# ============================================================
# Market Data Audit Thresholds
# ============================================================

MARKET_AUDIT_CONFIG = {

    "stale_data": {
        "warning_sessions": 1,
        "fail_sessions": 2,
        "critical_sessions": 5,
    },


    "missing_history": {
        "max_allowed_gap_sessions": 0,
    },


    "gap_detection": {
        "tolerance_threshold_pct": 0.05,
    },


    "corporate_actions": {
        "price_jump_threshold_pct": 20.0,
    },
}


# ============================================================
# Execution Environment
# ============================================================

AUDIT_ENVIRONMENT = {

    "default_exchange": "NSE",

    "timezone": "Asia/Kolkata",

    "strict_mode": True,

    "date_format": "%Y-%m-%d",

}


# ============================================================
# Database Configuration
# ============================================================

DATABASE_CONFIG = {

    "market_data": {
        "required_tables": [
            "prices"
        ],

        "required_indexes": [
            "idx_prices_symbol_date"
        ]
    }
}


# ============================================================
# Severity Levels
# ============================================================

AUDIT_SEVERITY = {

    "levels": [
        "PASS",
        "WARNING",
        "FAIL",
        "CRITICAL"
    ]

}


# ============================================================
# Scanner Ecosystem Configuration
# ============================================================
# Added to unblock RelativeStrengthEngine, Consolidation_Scanner,
# Emerging_Leader_Scanner, Hybrid_Alpha_Scanner, Earnings_Gap_Scanner,
# Cup_and_Handle, Master_Terminal, Breakout_Trigger_Scanner, and
# Market_Data_Cache, none of which could previously import.
#
# CONFIRMED values (verified against real local files/data):
BASE_DIR = r"C:\Users\GS102\OneDrive\Research\Invest\BETA\CoreUpgrade-forensic"
DB_PATH = str(Path(BASE_DIR) / "rs_delivery_history.db")   # confirmed canonical: 7,394 daily_snapshot rows, 62,671 scanner_factors rows, full downstream pipeline tables present
PARQUET_CACHE_DIR = str(Path(BASE_DIR) / "parquet_cache")   # confirmed exists, 4,009 files
UNIVERSE_CSV_PATH = str(Path(BASE_DIR) / "NSE_EQ.csv")       # confirmed exists, correct SYMBOL/SERIES columns
MASTER_OUTPUT_PATH = str(Path(BASE_DIR) / "RESEARCH_WATCHLIST.xlsx")
TRADE_PLAN_EXCEL = str(Path(BASE_DIR) / "TRADE_PLAN.xlsx")   # confirmed exists as a real file already
MIN_DAILY_TURNOVER = 3e7   # Rs 3 crore - matches existing precedent in alpha_pipeline_orchestrator.py

# PROPOSED DEFAULTS - these are business/strategy judgment calls, not
# discovered values. Review and adjust before relying on scanner output.
MIN_PRICE = 20.0            # penny-stock floor filter (Rs)
VOLUME_SMA_PERIOD = 20      # trading days, for Earnings_Gap_Scanner's volume baseline
MIN_TRADING_DAYS_RS = 252   # must be >= 250 (RelativeStrengthEngine directly indexes iloc[-250]);
                             # set to match alpha_pipeline_orchestrator.py's own 252-day gate
CACHE_HISTORY_PERIOD = "2y" # yfinance period string; only relevant to Market_Data_Cache.py,
                             # which may become obsolete once the bhav-copy converter exists
RVOL_TRIGGER_LIMIT = 1.5    # relative-volume multiplier for Breakout_Trigger_Scanner's live intraday check

# Breakout_Trigger_Scanner-specific values, discovered after RISK_PCT etc.
# surfaced behind the yfinance import gap:
PIVOT_BUFFER_PCT = 0.3      # % buffer above pivot before confirming a valid trigger

RISK_REWARD_RATIO = 2.0     # minimum reward:risk multiple for target price calc

# NOTE: RISK_PCT is capital-at-risk-per-trade (position sizing), NOT the same
# thing as your 5% stop-loss distance. capital * RISK_PCT = rupees risked if
# stopped out. Standard practice is 0.5-2% of capital per trade, not 5% -
# reusing the 5% stop distance here would be a materially different,
# much more aggressive decision. Review before trading on this.
RISK_PCT = 0.01

CONVICTION_WEIGHTS = {       # must sum to 1.0 (raw_conv is scaled by 10.0 after)
    "leadership": 0.35,
    "structure": 0.30,
    "tape": 0.20,
    "risk": 0.15,
}

# Reused directly from Market_Regime_Engine.py's own internal exposure
# mapping (not invented separately) - same regime labels, same values.
REGIME_MULTIPLIERS = {
    "CONFIRMED_UPTREND": 1.00,
    "EARLY_RECOVERY": 0.50,
    "CHOPPY_ACCUMULATION": 0.60,
    "DISTRIBUTION": 0.25,
    "BEAR": 0.25,
}