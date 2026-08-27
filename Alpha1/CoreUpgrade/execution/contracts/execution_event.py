# execution/contracts/execution_event.py
import dataclasses
from datetime import datetime
from decimal import Decimal
from research.governance.serialization import CanonicalSerializer

@dataclasses.dataclass(frozen=True)
class ExecutionEvent:
    """
    Immutable notification from exchange/broker gateways driving event-driven OMS state changes.
    Ensures the OMS updates state based on verifiable execution events rather than manual overrides.
    """
    event_id: str
    order_id: str
    intent_id: str
    event_type: str        # e.g., "ORDER_ACCEPTED", "PARTIAL_FILL", "FULL_FILL", "ORDER_REJECTED", "CANCEL_CONFIRMED"
    fill_price: Decimal | None
    fill_quantity: Decimal | None
    remaining_quantity: Decimal | None
    timestamp: datetime
    raw_message: str       # Vendor or broker payload string representation

    @property
    def event_hash(self) -> str:
        """Cryptographic fingerprint for execution event auditing and event sourcing logs."""
        return CanonicalSerializer.hash(self)
