# research/data/temporal_tracker.py
import dataclasses
from typing import List, Optional
from datetime import datetime

@dataclasses.dataclass
class FeatureAccessEvent:
    column: str
    usage_category: str            # "signal", "execution", "sizing"
    decision_timestamp: datetime   # Simulation clock (T)
    requested_timestamp: datetime  # Data point accessed
    lag: int                       # Distance from T (0 = today, -1 = yesterday, 1 = tomorrow)
    
class TemporalDependencyTracker:
    def __init__(self):
        self.access_log: List[FeatureAccessEvent] = []
        
    def record_access(self, event: FeatureAccessEvent):
        self.access_log.append(event)
        
    def inspect(self) -> dict:
        # Group and summarize the access log for the governance engine
        return {
            "total_access_events": len(self.access_log),
            "future_leaks": [e for e in self.access_log if e.lag > 0],
            "valid_historical_access": [e for e in self.access_log if e.lag <= 0]
        }
