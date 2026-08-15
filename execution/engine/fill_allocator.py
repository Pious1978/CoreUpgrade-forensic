from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4, UUID
from typing import Callable, Tuple

from execution.contracts.fill_contract import FillContract
from execution.contracts.order_contract import OrderContract
from execution.models.contracts.liquidity_assessment import LiquidityAssessment
from execution.models.contracts.price_adjustment import PriceAdjustment
from execution.simulation.context import ExecutionSimulationContext

@dataclass(frozen=True, slots=True)
class BaselineFillAllocator:
    """
    Baseline fill allocation engine dedicated purely to determining 
    filled quantities and generating atomic execution tranches.
    """
    execution_id_generator: Callable[[], UUID] = uuid4
    fill_id_generator: Callable[[], UUID] = uuid4

    def allocate(
        self,
        order: OrderContract,
        context: ExecutionSimulationContext,
        liquidity: LiquidityAssessment,
        price_adjustment: PriceAdjustment,
    ) -> tuple[FillContract, ...]:
        """
        Calculates executable quantities and produces immutable atomic fill tranches.
        """
        if liquidity.fill_probability <= Decimal("0") or liquidity.available_quantity <= Decimal("0"):
            return tuple()

        filled_qty = min(order.quantity, liquidity.available_quantity)
        if filled_qty <= Decimal("0"):
            return tuple()

        execution_id = self.execution_id_generator()
        base_price = context.market_snapshot.last_price
        execution_price = base_price + price_adjustment.total

        fill = FillContract(
            fill_id=self.fill_id_generator(),
            execution_id=execution_id,
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            quantity=filled_qty,
            price=execution_price,
            timestamp=context.market_snapshot.timestamp,
            fee=Decimal("0"),  # Fees are handled downstream by the fee model
        )

        return (fill,)
