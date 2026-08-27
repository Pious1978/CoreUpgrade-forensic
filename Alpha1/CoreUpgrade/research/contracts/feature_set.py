from dataclasses import dataclass, field
from typing import Dict, Any
from datetime import datetime

@dataclass(frozen=True)
class FeatureSet:
    snapshot_hash: str
    features: Dict[str, float]
    computation_timestamp: datetime
