#!/usr/bin/env python3
"""
audits/market_data/config.py
Configuration parameters, validation thresholds, output paths, and schema definitions 
for institutional market data auditing.
"""

MARKET_AUDIT_CONFIG = {
    "databases": [
        "market_data.db"
    ],
    "thresholds": {
        "max_volume_spike_multiplier": 500.0,
        "max_price_spike_pct": 50.0,
        "stale_data_max_days": 3,
        "max_consecutive_flat_prices": 10,
        "missing_session_tolerance": 5,
        "split_detection_threshold_pct": 40.0,
        "coverage_pass_pct": 99.5,
        "coverage_warning_pct": 95.0
    },
    "outputs": {
        "repair_queue_file": "reports/repair_queue.json"
    },
    "required_columns": {
        "prices": ["Symbol", "Date", "Open", "High", "Low", "Close", "Volume"],
        "delivery": ["Symbol", "Date", "DeliveryQuantity", "TradedQuantity"]
    },
    "liquidity_grades": {
        "A_PLUS": {"min_traded_value": 100000000, "min_delivery_pct": 50.0},
        "A": {"min_traded_value": 25000000, "min_delivery_pct": 30.0},
        "B": {"min_traded_value": 5000000, "min_delivery_pct": 15.0},
        "C": {"min_traded_value": 1000000, "min_delivery_pct": 5.0},
        "D": {"min_traded_value": 0, "min_delivery_pct": 0.0}
    }
}
