from datetime import datetime, timezone

class MarketDataFreshnessMonitor:
    """Enforces strict data latency limits before allowing execution."""
    
    MAX_DATA_AGE_SECONDS = 5.0  # Maximum acceptable feed latency

    @classmethod
    def check_freshness(cls, data_timestamp: datetime, current_time: datetime = None) -> dict:
        current_time = current_time or datetime.now(timezone.utc)
        
        if data_timestamp.tzinfo is None and current_time.tzinfo is not None:
            data_timestamp = data_timestamp.replace(tzinfo=timezone.utc)
        elif data_timestamp.tzinfo is not None and current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        
        age_seconds = (current_time - data_timestamp).total_seconds()
        
        if age_seconds > cls.MAX_DATA_AGE_SECONDS:
            return {
                "status": "STALE",
                "fresh": False,
                "age_seconds": round(age_seconds, 2),
                "action": "BLOCK_EXECUTION"
            }
        return {
            "status": "FRESH",
            "fresh": True,
            "age_seconds": round(age_seconds, 2),
            "action": "ALLOW_EXECUTION"
        }
