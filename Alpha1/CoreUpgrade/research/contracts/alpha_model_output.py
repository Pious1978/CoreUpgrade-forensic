from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class AlphaModelOutput:
    model_id: str
    raw_score: float
    confidence_interval: float
    regime_state: str
    computation_timestamp: datetime
