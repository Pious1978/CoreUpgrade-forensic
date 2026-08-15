from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class ResearchSignalContract:
    """Public boundary contract between Research and Portfolio."""
    symbol: str
    direction: int  # 1 (Long), -1 (Short)
    strength_score: float
    artifact_hash: str
    generated_at: datetime
