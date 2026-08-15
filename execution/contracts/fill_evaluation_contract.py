from decimal import Decimal
from dataclasses import dataclass
from typing import Tuple

from execution.contracts.market_snapshot_contract import MarketSnapshotContract
from execution.simulation.context import ExecutionSimulationContext
from brokers.paper.contracts import FillContract

@dataclass(frozen=True, slots=True)
class FillEvaluationResult:
    status: OrderStatus
    fills: Tuple[FillContract, ...]
    remaining_quantity: Decimal
    average_price: Decimal
    slippage: Decimal
    fees: Decimal
    warnings: Tuple[str, ...] = ()
