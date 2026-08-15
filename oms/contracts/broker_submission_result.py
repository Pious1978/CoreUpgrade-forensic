from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True, slots=True)
class BrokerSubmissionResult:
    """Immutable contract capturing the successful submission of an order to a broker."""
    broker_order_id: str
    accepted_at: datetime
    exchange_order_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.broker_order_id.strip():
            raise ValueError("broker_order_id cannot be empty")
        if self.accepted_at.tzinfo is None:
            raise ValueError("accepted_at must be timezone-aware")
