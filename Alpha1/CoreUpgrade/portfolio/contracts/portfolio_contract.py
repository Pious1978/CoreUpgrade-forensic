from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from portfolio.contracts.position_target_contract import PositionTargetContract

@dataclass(frozen=True, slots=True)
class PortfolioContract:
    """
    Immutable portfolio allocation artifact produced after strategy certification,
    incorporating model versioning, currency designation, and strict weight conservation invariants.
    """
    portfolio_id: str
    strategy_id: str
    construction_model_version: str
    currency: str
    targets: tuple[PositionTargetContract, ...]
    cash_weight: Decimal
    timestamp: datetime

    def __post_init__(self) -> None:
        if not self.portfolio_id:
            raise ValueError("Portfolio ID cannot be empty.")
        if not self.strategy_id:
            raise ValueError("Strategy ID cannot be empty.")
        if not self.construction_model_version:
            raise ValueError("Construction model version cannot be empty.")
        if not self.currency:
            raise ValueError("Currency cannot be empty.")
        if not (Decimal("0") <= self.cash_weight <= Decimal("1")):
            raise ValueError("Cash weight must be between 0 and 1.")

        total_weight = (
            sum(
                (target.target_weight for target in self.targets),
                Decimal("0"),
            )
            + self.cash_weight
        )

        if abs(total_weight - Decimal("1")) > Decimal("0.0001"):
            raise ValueError(f"Portfolio weights and cash must equal 1.0. Got {total_weight}")
