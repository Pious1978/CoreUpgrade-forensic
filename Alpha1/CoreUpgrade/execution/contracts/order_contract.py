# execution/contracts/order_contract.py
import dataclasses
from datetime import datetime
from decimal import Decimal
from research.governance.serialization import CanonicalSerializer

@dataclasses.dataclass(frozen=True)
class OrderIntent:
    """
    Represents an atomic child order routed through the Order Management System (OMS).
    Derived from an ExecutionIntent via intelligent slicing, but strictly bound to 
    the parent intent's authorization tree.
    """
    order_id: str
    intent_id: str             # Cryptographic or ID reference to parent ExecutionIntent
    portfolio_id: str
    instrument_id: str
    side: str                  # "BUY" or "SELL"
    quantity: Decimal          # Absolute slice quantity
    order_type: str            # "MARKET", "LIMIT", "TWAP_CHILD"
    limit_price: Decimal | None
    exchange: str              # e.g., "NSE", "BSE"
    timestamp: datetime

    def __post_init__(self):
        if self.quantity <= Decimal("0"):
            raise ValueError("OrderIntent quantity must be strictly greater than zero.")
        if self.side not in ("BUY", "SELL"):
            raise ValueError(f"Invalid order side: {self.side}. Must be 'BUY' or 'SELL'.")

    @property
    def order_hash(self) -> str:
        """Cryptographic fingerprint for order auditing and OMS state tracking."""
        return CanonicalSerializer.hash(self)
