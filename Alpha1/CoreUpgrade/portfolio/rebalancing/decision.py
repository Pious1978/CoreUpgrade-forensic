from dataclasses import dataclass, field
from typing import Dict, Any, List

@dataclass(frozen=True)
class PortfolioDecision:
    """
    Immutable institutional decision record. Enriched sequentially by optimizer, 
    risk engine, capacity analyzer, execution simulator, and governance gatekeeper.
    """
    experiment_id: str
    timestamp: str
    portfolio_before: Dict[str, Any] = field(default_factory=dict)
    optimizer_result: Dict[str, Any] = field(default_factory=dict)
    risk_result: Dict[str, Any] = field(default_factory=dict)
    capacity_result: Dict[str, Any] = field(default_factory=dict)
    execution_result: Dict[str, Any] = field(default_factory=dict)
    constraint_violations: List[Dict[str, Any]] = field(default_factory=list)
    final_orders: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def enrich(self, **kwargs) -> "PortfolioDecision":
        """Returns a new immutable instance with updated fields (Functional Copy Pattern)."""
        data = {
            "experiment_id": self.experiment_id,
            "timestamp": self.timestamp,
            "portfolio_before": self.portfolio_before,
            "optimizer_result": self.optimizer_result,
            "risk_result": self.risk_result,
            "capacity_result": self.capacity_result,
            "execution_result": self.execution_result,
            "constraint_violations": self.constraint_violations,
            "final_orders": self.final_orders,
            "metadata": self.metadata
        }
        data.update(kwargs)
        return PortfolioDecision(**data)
