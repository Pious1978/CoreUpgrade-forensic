from dataclasses import dataclass
from decimal import Decimal
from execution.contracts.order_contract import OrderContract, OrderSide
from execution.simulation.context import ExecutionSimulationContext
from execution.models.contracts.liquidity_assessment import LiquidityAssessment

@dataclass(frozen=True, slots=True)
class BaselineSlippageModel:
    """
    Baseline deterministic slippage model computing price adjustments 
    from market spread components and volatility scaling.
    """
    volatility_impact_factor: Decimal = Decimal("0.01")

    def calculate(
        self,
        order: OrderContract,
        context: ExecutionSimulationContext,
        liquidity: LiquidityAssessment,
    ) -> Decimal:
        """
        Calculates the slippage price adjustment value based on order direction,
        bid-ask spread, and context volatility.
        """
        snapshot = context.market_snapshot
        spread = snapshot.ask - snapshot.bid
        half_spread = spread / Decimal("2")

        # Volatility adjustment scaling
        vol_adjustment = snapshot.last_price * context.volatility * self.volatility_impact_factor

        total_slippage_magnitude = half_spread + vol_adjustment

        # Directional adjustment: BUY orders slip upward (+), SELL orders slip downward (-)
        if order.side == OrderSide.BUY:
            return total_slippage_magnitude
        else:
            return -total_slippage_magnitude
