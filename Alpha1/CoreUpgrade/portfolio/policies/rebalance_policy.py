from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True, slots=True)
class RebalancePolicy:
    """
    Defines thresholds and rules governing whether a position delta 
    warrants emitting a rebalance instruction.
    """
    minimum_quantity_change: Decimal = Decimal("0.0001")
    rebalance_reason: str = "STRATEGY_SIGNAL_CHANGE"

    def __post_init__(self) -> None:
        if self.minimum_quantity_change < Decimal("0"):
            raise ValueError("Minimum quantity change cannot be negative.")
        if not self.rebalance_reason:
            raise ValueError("Rebalance reason cannot be empty.")
