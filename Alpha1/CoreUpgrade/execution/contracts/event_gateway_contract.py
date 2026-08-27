# execution/contracts/event_gateway_contract.py
import dataclasses
from datetime import datetime
from typing import Dict, Any
from research.governance.serialization import CanonicalSerializer

@dataclasses.dataclass(frozen=True)
class GatewayIngressPayload:
    """
    Immutable contract representing a raw, unvalidated message received 
    from an external broker or exchange gateway.
    Acts as the secure ingress point before normalization and event validation.
    """
    ingress_id: str
    broker_name: str
    raw_payload: Dict[str, Any]
    received_timestamp: datetime

    @property
    def ingress_hash(self) -> str:
        """Cryptographic fingerprint of the raw ingress message for audit trails."""
        return CanonicalSerializer.hash(self)
