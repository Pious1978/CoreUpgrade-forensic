# execution/contracts/order_event_record.py
import dataclasses
from datetime import datetime
from execution.oms.order_state_machine import OrderState
from research.governance.serialization import CanonicalSerializer

@dataclasses.dataclass(frozen=True)
class OrderEventRecord:
    """
    Immutable audit record of a verified OMS state transition.
    Forms the cryptographic foundation for event sourcing, 
    disaster recovery, and broker reconciliation.
    """
    event_id: str
    order_id: str
    previous_state: OrderState
    new_state: OrderState
    timestamp: datetime
    event_hash: str  # Hash of the triggering ExecutionEvent payload

    @property
    def record_hash(self) -> str:
        """Cryptographic fingerprint for the state transition log."""
        return CanonicalSerializer.hash(self)
