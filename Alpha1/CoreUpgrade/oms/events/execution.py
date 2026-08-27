from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar

from oms.events.base import BaseOrderEvent


@dataclass(frozen=True, slots=True)
class TradeFillEvent(BaseOrderEvent):
    """Immutable accounting fact representing a specific execution."""
    SCHEMA_VERSION: ClassVar[int] = 1

    broker_order_id: str
    fill_id: str
    fill_quantity: Decimal
    fill_price: Decimal
    gross_notional: Decimal
    commission: Decimal
    fees: Decimal
    net_cash_change: Decimal  # Positive for sell proceeds, negative for buy costs
