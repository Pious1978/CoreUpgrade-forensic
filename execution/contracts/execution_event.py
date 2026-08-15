# execution/contracts/execution_event.py

import dataclasses
from datetime import datetime
from decimal import Decimal

from research.governance.serialization import CanonicalSerializer


@dataclasses.dataclass(frozen=True)
class ExecutionEvent:
    event_id: str
    order_id: str
    intent_id: str
    event_type: str
    timestamp: datetime
    raw_message: str
    fill_price: Decimal | None = None
    fill_quantity: Decimal | None = None
    remaining_quantity: Decimal | None = None

    @property
    def event_hash(self) -> str:
        """Cryptographic fingerprint for execution event auditing and event sourcing logs."""
        return CanonicalSerializer.hash(self)