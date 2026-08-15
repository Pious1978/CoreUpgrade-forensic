from dataclasses import dataclass
from decimal import Decimal
from execution.contracts.order_contract import OrderContract
from execution.simulation.context import ExecutionSimulationContext
from execution.models.contracts.liquidity_assessment import LiquidityAssessment

@dataclass(frozen=True, slots=True)
class BaselineLiquidityModel:
    """
    Baseline liquidity evaluation model calculating available volume 
    via participation limits and deriving realistic fill probabilities.
    """
    participation_limit: Decimal = Decimal("0.05")  # Default 5% participation threshold

    def evaluate(
        self,
        order: OrderContract,
        context: ExecutionSimulationContext,
    ) -> LiquidityAssessment:
        """
        Evaluates liquidity constraints for a given order intent against the simulation context.
        """
        # Derived available depth capacity from snapshot volume and participation limit
        available_qty = context.market_snapshot.volume * self.participation_limit

        if available_qty == Decimal("0"):
            fill_prob = Decimal("0")
        else:
            # Scale fill probability based on order size pressure relative to available depth
            ratio = min(order.quantity / available_qty, Decimal("1"))
            fill_prob = context.liquidity_score * (Decimal("1") - (ratio * Decimal("0.2")))
            fill_prob = max(Decimal("0"), min(fill_prob, Decimal("1")))

        return LiquidityAssessment(
            available_quantity=available_qty,
            fill_probability=fill_prob,
            liquidity_score=context.liquidity_score,
        )
