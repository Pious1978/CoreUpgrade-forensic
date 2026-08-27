from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True, slots=True)
class FeeAssessment:
    total_fee: Decimal
    exchange_fee: Decimal
    broker_commission: Decimal
    regulatory_fee: Decimal
    flat_fee: Decimal

    def __post_init__(self) -> None:
        if self.total_fee < Decimal("0"):
            raise ValueError("Total fee cannot be negative.")
        if self.exchange_fee < Decimal("0"):
            raise ValueError("Exchange fee cannot be negative.")
        if self.broker_commission < Decimal("0"):
            raise ValueError("Broker commission cannot be negative.")
        if self.regulatory_fee < Decimal("0"):
            raise ValueError("Regulatory fee cannot be negative.")
        if self.flat_fee < Decimal("0"):
            raise ValueError("Flat fee cannot be negative.")
