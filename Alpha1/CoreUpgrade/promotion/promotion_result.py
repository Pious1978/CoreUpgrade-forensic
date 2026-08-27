from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

@dataclass(frozen=True)
class PromotionResult:
    """Standardized bundle containing all generated immutable contracts and execution metrics."""
    contracts: Tuple[Any, ...]
    metrics: Dict[str, Any] = field(default_factory=dict)
    promotion_time: float = 0.0
    duration_ms: float = 0.0
    success: bool = True

    @property
    def source(self) -> Any:
        return self.contracts[0] if len(self.contracts) > 0 else None

    @property
    def transitioned_source(self) -> Any:
        return self.contracts[1] if len(self.contracts) > 1 else None

    @property
    def decision(self) -> Any:
        return self.contracts[2] if len(self.contracts) > 2 else None

    @property
    def target(self) -> Any:
        return self.contracts[3] if len(self.contracts) > 3 else None

    @property
    def audit(self) -> Any:
        return self.contracts[4] if len(self.contracts) > 4 else None
