from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

class RebalanceAction(Enum):
    BUY = "BUY"
    SELL = "SELL"

@dataclass(frozen=True, slots=True)
class RebalanceInstructionContract:
    """
    Immutable, noise-filtered rebalance directive derived from portfolio delta 
    calculations, carrying explicit audit reasons.
    """
    instruction_id: str
    portfolio_id: str
    symbol: str
    action: RebalanceAction
    current_quantity: Decimal
    target_quantity: Decimal
    signed_delta_quantity: Decimal  # Positive for BUY, negative for SELL
    reason: str

    def __post_init__(self) -> None:
        if not self.instruction_id:
            raise ValueError("Instruction ID cannot be empty.")
        if not self.portfolio_id:
            raise ValueError("Portfolio ID cannot be empty.")
        if not self.symbol:
            raise ValueError("Symbol cannot be empty.")
        if not self.reason:
            raise ValueError("Reason cannot be empty.")
        if self.current_quantity < Decimal("0"):
            raise ValueError("Current quantity cannot be negative.")
        if self.target_quantity < Decimal("0"):
            raise ValueError("Target quantity cannot be negative.")

        expected_delta = self.target_quantity - self.current_quantity
        if abs(self.signed_delta_quantity - expected_delta) > Decimal("0.0001"):
            raise ValueError("Signed delta quantity does not match target minus current.")

        if self.signed_delta_quantity > Decimal("0") and self.action != RebalanceAction.BUY:
            raise ValueError("Positive delta requires action to be BUY.")
        elif self.signed_delta_quantity < Decimal("0") and self.action != RebalanceAction.SELL:
            raise ValueError("Negative delta requires action to be SELL.")
