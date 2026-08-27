from dataclasses import dataclass
from decimal import Decimal

from execution.contracts.order_contract import OrderContract
from execution.contracts.fill_decision_contract import FillDecisionContract
from execution.simulation.context import ExecutionSimulationContext
from execution.models.protocols import (
    LiquidityModelProtocol,
    SlippageModelProtocol,
    MarketImpactModelProtocol,
    FeeModelProtocol,
)
from execution.models.contracts.price_adjustment import PriceAdjustment
from execution.engine.fill_allocator import BaselineFillAllocator
from execution.engine.fill_decision_assembler import FillDecisionAssembler

@dataclass(frozen=True, slots=True)
class FillSimulationEngine:
    """
    Core deterministic simulation engine cleanly orchestrating liquidity, 
    slippage, market impact, allocation, fee assessment, and decision assembly.
    """
    liquidity_model: LiquidityModelProtocol
    slippage_model: SlippageModelProtocol
    impact_model: MarketImpactModelProtocol
    fee_model: FeeModelProtocol
    fill_allocator: BaselineFillAllocator
    decision_assembler: FillDecisionAssembler = FillDecisionAssembler()

    def simulate(
        self,
        order: OrderContract,
        context: ExecutionSimulationContext,
    ) -> FillDecisionContract:
        """
        Orchestrates the single-pass deterministic simulation pipeline.
        """
        # 1. Evaluate Liquidity
        liquidity = self.liquidity_model.evaluate(order, context)

        # 2. Calculate Price Adjustments
        slippage_adjustment = self.slippage_model.calculate(order, context, liquidity)
        impact_adjustment = self.impact_model.calculate(order, context, liquidity)

        price_adjustment = PriceAdjustment(
            spread_component=slippage_adjustment.spread_component,
            volatility_component=slippage_adjustment.volatility_component,
            impact_component=impact_adjustment.impact_component,
        )

        # 3. Allocate Fills (Single Pass)
        fills = self.fill_allocator.allocate(
            order=order,
            context=context,
            liquidity=liquidity,
            price_adjustment=price_adjustment,
        )

        # 4. Calculate Fees Downstream from Actual Fills
        fee_assessment = self.fee_model.calculate(fills, context)

        # 5. Assemble Final Aggregate Decision Outcome
        decision = self.decision_assembler.assemble(
            order=order,
            fills=fills,
            fee_assessment=fee_assessment,
        )

        return decision
