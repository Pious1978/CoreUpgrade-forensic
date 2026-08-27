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
