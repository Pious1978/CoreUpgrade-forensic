AUDIT_CONFIG = {
    "databases": [
        "market_data.db",
        "research.db",
        "historical_snapshots.db",
        "target_database.db",
        "audit_history.db"
    ],
    "expected_symbol_count": 563,
    "thresholds": {
        "max_row_drop": 1000000,
        "max_size_growth_pct": 50.0,
        "max_null_pct": 5.0,
        "max_free_page_pct": 20.0
    },
    "required_tables": {
        "market_data.db": ["prices", "fundamentals", "delivery"],
        "research.db": ["research", "financials"],
        "target_database.db": ["targets"],
        "audit_history.db": ["audit_log", "metric_history"],
        "historical_snapshots.db": []
    },
    "expected_schemas": {
        "market_data.db": {
            "prices": {
                "cols": {"Symbol": "TEXT", "Date": "TEXT", "Open": "REAL", "High": "REAL", "Low": "REAL", "Close": "REAL", "Volume": "INTEGER"},
                "pks": ["Symbol", "Date"]
            },
            "delivery": {
                "cols": {"Symbol": "TEXT", "Date": "TEXT", "DeliveryQuantity": "INTEGER", "TradedQuantity": "INTEGER"},
                "pks": ["Symbol", "Date"]
            }
        },
        "research.db": {
            "research": {
                "cols": {"Symbol": "TEXT", "RS_Score": "REAL", "CompositeScore": "REAL"},
                "pks": ["Symbol"]
            }
        }
    }
}
