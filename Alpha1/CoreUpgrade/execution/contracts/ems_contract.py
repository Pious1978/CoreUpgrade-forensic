# execution/contracts/ems_contract.py
import dataclasses
from datetime import datetime
from decimal import Decimal
from research.governance.serialization import CanonicalSerializer

@dataclasses.dataclass(frozen=True)
class EMSOrderRequest:
    """
    Standardized, broker-agnostic translation of an authorized OrderIntent.
    Dispatched from the OMS/EMS boundary to concrete broker adapters.
    Contains zero visibility into upstream alpha models, portfolio optimization, or risk weights.
    """
    ems_request_id: str
    order_id: str          # Links directly to OMS OrderIntent / OrderRecord
    portfolio_id: str
    instrument_id: str
    side: str              # "BUY" or "SELL"
    quantity: Decimal
    order_type: str        # "MARKET", "LIMIT"
    limit_price: Decimal | None
    exchange: str          # Target routing venue e.g., "NSE", "BSE"
    routing_instructions: str | None # e.g., "IOC", "DAY", "ALGO_TWAP"
    timestamp: datetime

    def __post_init__(self):
        if self.quantity <= Decimal("0"):
            raise ValueError("EMSOrderRequest quantity must be strictly greater than zero.")
        if self.side not in ("BUY", "SELL"):
            raise ValueError(f"Invalid EMS order side: {self.side}")

    @property
    def request_hash(self) -> str:
        """Cryptographic fingerprint for EMS request routing audit trails."""
        return CanonicalSerializer.hash(self)
