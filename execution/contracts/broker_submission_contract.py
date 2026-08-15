# execution/contracts/broker_submission_contract.py
import dataclasses
from datetime import datetime
from research.governance.serialization import CanonicalSerializer

@dataclasses.dataclass(frozen=True)
class BrokerSubmissionResult:
    """
    Standardized receipt returned by a concrete broker adapter 
    upon dispatching an EMSOrderRequest. Mandates unbroken request lineage.
    """
    submission_id: str
    ems_request_hash: str  # Always mandatory and non-empty for full audit tracking
    broker_name: str
    broker_order_id: str | None
    status: str             # e.g., "SUBMITTED", "CANCEL_REQUESTED", "REJECTED"
    reject_reason: str | None
    timestamp: datetime

    def __post_init__(self):
        if not self.ems_request_hash:
            raise ValueError(
                "BrokerSubmissionResult invariant violated: "
                "ems_request_hash cannot be empty. Lineage binding is mandatory."
            )

    @property
    def receipt_hash(self) -> str:
        """Cryptographic fingerprint for submission auditing."""
        return CanonicalSerializer.hash(self)
