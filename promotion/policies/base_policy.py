from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

@dataclass(frozen=True)
class PolicyEvaluationResult:
    passed: bool
    score: float
    reason: str
    warnings: Tuple[str, ...] = ()
    violations: Tuple[str, ...] = ()
    version: str = "2.3.0"
    metadata: Dict[str, Any] = field(default_factory=dict)

class BasePromotionPolicy(ABC):
    @abstractmethod
    def evaluate(self, source: Any, context: Any) -> PolicyEvaluationResult:
        pass
