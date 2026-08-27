# execution/contracts/execution_intent.py
import dataclasses
from datetime import datetime
from decimal import Decimal
from research.governance.serialization import CanonicalSerializer

@dataclasses.dataclass(frozen=True)
class ExecutionIntent:
    """
    Immutable instruction translating a certified portfolio delta into a specific market action.
    Derived exclusively from a valid PortfolioCertificate. Prevents unauthorized or rogue orders.
    """
    intent_id: str
    portfolio_certificate_hash: str
    portfolio_id: str
    instrument_id: str
    current_position: Decimal
    target_position: Decimal
    delta_quantity: Decimal  # Positive for BUY, Negative for SELL
    urgency: str             # e.g., "LOW", "MEDIUM", "HIGH", "TWAP"
    execution_policy_id: str
    timestamp: datetime

    def __post_init__(self):
        # Enforce mathematical consistency of the delta
        calculated_delta = self.target_position - self.current_position
        if self.delta_quantity != calculated_delta:
            raise ValueError(
                f"ExecutionIntent delta invariant violated: delta_quantity ({self.delta_quantity}) "
                f"must equal target_position ({self.target_position}) - current_position ({self.current_position})."
            )

    @property
    def intent_hash(self) -> str:
        """Cryptographic fingerprint for execution auditing and replay."""
        return CanonicalSerializer.hash(self)
