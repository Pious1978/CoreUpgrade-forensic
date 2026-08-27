from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class AccountContract:
    broker_name: str
    cash_balance: Decimal
    buying_power: Decimal
    margin_used: Decimal
    timestamp: int

    def __post_init__(self):
        if self.cash_balance < 0:
            raise ValueError("Cash balance cannot be negative")
        if self.buying_power < 0:
            raise ValueError("Buying power cannot be negative")
