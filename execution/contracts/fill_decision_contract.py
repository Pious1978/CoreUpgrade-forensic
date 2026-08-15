from decimal import Decimal
from dataclasses import dataclass
from enum import Enum
from execution.contracts.fill_contract import FillContract

class FillStatus(Enum):
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    REJECTED = "REJECTED"

@dataclass(frozen=True, slots=True)
class FillDecisionContract:
    """
    Represents the simulated outcome of an order execution request.
    
    Invariants:
        1. requested_quantity == filled_quantity + remaining_quantity
        2. execution_price == base_price + slippage_adjustment + market_impact_adjustment
        3. 0 <= execution_probability <= 1
        4. fees >= 0
        5. FILLED status requires remaining_quantity == 0
        6. REJECTED status requires filled_quantity == 0
    """

    status: FillStatus
    fills: tuple[FillContract, ...]

    requested_quantity: Decimal
    filled_quantity: Decimal
    remaining_quantity: Decimal

    base_price: Decimal
    execution_price: Decimal

    slippage_adjustment: Decimal
    market_impact_adjustment: Decimal

    execution_probability: Decimal
    fees: Decimal

    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.requested_quantity != self.filled_quantity + self.remaining_quantity:
            raise ValueError(
                "Quantity invariant violated: requested != filled + remaining."
            )

        if not (Decimal("0") <= self.execution_probability <= Decimal("1")):
            raise ValueError("Execution probability must be between 0 and 1.")

        if self.fees < Decimal("0"):
            raise ValueError("Fees cannot be negative.")

        expected_price = (
            self.base_price
            + self.slippage_adjustment
            + self.market_impact_adjustment
        )

        if expected_price != self.execution_price:
            raise ValueError(
                "Execution price invariant violated: expected != actual execution price."
            )

        if self.status == FillStatus.FILLED and self.remaining_quantity != Decimal("0"):
            raise ValueError("FILLED status requires zero remaining quantity.")

        if self.status == FillStatus.REJECTED and self.filled_quantity != Decimal("0"):
            raise ValueError("REJECTED status cannot contain fills.")

    @property
    def fill_ratio(self) -> Decimal:
        if self.requested_quantity == Decimal("0"):
            return Decimal("0")
        return self.filled_quantity / self.requested_quantity
