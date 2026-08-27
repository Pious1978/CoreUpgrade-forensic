from dataclasses import dataclass, field
from typing import Any, Mapping
from .metadata import PromotionMetadata
from .trace import TraceTree
from .status import PromotionStatus

@dataclass(frozen=True)
class PromotionResult:
    """Pure type definition for promotion execution results."""
    source: Any
    transitioned_source: Any
    decision: Any
    target: Any
    audit: Any
    metadata: PromotionMetadata
    trace: TraceTree
    status: PromotionStatus = PromotionStatus.COMMITTED
    metrics: Mapping[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    success: bool = True
