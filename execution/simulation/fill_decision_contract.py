from decimal import Decimal
from dataclasses import dataclass
from typing import Tuple
from brokers.paper.contracts import FillContract

@dataclass(frozen=True, slots=True)
class FillDecisionContract:
    status: str  # FILLED, PARTIALLY_FILLED, REJECTED
    fills: Tuple[FillContract, ...]
    requested_quantity: Decimal
    filled_quantity: Decimal
    remaining_quantity: Decimal
    base_price: Decimal
    execution_price: Decimal
    slippage_adjustment: Decimal
    market_impact_adjustment: Decimal
    execution_probability: Decimal
    fees: Decimal
    warnings: Tuple[str, ...] = ()
