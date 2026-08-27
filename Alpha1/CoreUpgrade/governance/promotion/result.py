from dataclasses import dataclass, field
from typing import List

@dataclass(frozen=True)
class PromotionResult:
    symbol: str
    approved: bool
    reasons: List[str] = field(default_factory=list)
    failed_rules: List[str] = field(default_factory=list)
    score: float = 0.0
