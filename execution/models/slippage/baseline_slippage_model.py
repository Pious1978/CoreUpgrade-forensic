from dataclasses import dataclass
from decimal import Decimal
from execution.contracts.order_contract import OrderContract, OrderSide
from execution.simulation.context import ExecutionSimulationContext
from execution.models.contracts.liquidity_assessment import LiquidityAssessment
from execution.models.contracts.price_adjustment import PriceAdjustment

@dataclass(frozen=True, slots=True)
class BaselineSlippageModel:
    """
    Baseline deterministic slippage model computing structured price components 
    from market spread components and volatility scaling.
    """
    volatility_impact_factor: Decimal = Decimal("0.01")

    def __post_init__(self) -> None:
        if self.volatility_impact_factor < Decimal("0"):
            raise ValueError("Volatility impact factor cannot be negative.")

    def calculate(
        self,
        order: OrderContract,
        context: ExecutionSimulationContext,
        liquidity: LiquidityAssessment,
    ) -> PriceAdjustment:
        """
        Calculates structured price adjustments separating spread and volatility metrics,
        applying directional sign scaling based on order side.
        """
        snapshot = context.market_snapshot
        spread = snapshot.ask - snapshot.bid
        half_spread = spread / Decimal("2")

        # Volatility adjustment scaling
        vol_adjustment = snapshot.last_price * context.volatility * self.volatility_impact_factor

        # Directional scaling: BUY orders slip upward (+), SELL orders slip downward (-)
        multiplier = Decimal("1") if order.side == OrderSide.BUY else Decimal("-1")

        return PriceAdjustment(
            spread_component=half_spread * multiplier,
            volatility_component=vol_adjustment * multiplier,
            impact_component=Decimal("0"),
        )
