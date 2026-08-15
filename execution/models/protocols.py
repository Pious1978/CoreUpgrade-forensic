from decimal import Decimal
from typing import Protocol, Tuple

from execution.contracts.liquidity_assessment_contract import LiquidityAssessment
from execution.contracts.order_contract import OrderContract
from execution.contracts.fill_contract import FillContract
from execution.models.contracts.fee_assessment import FeeAssessment
from execution.simulation.context import ExecutionSimulationContext


class LiquidityModelProtocol(Protocol):
    """Protocol defining the interface for market liquidity evaluation models."""
    def evaluate(
        self,
        order: OrderContract,
        context: ExecutionSimulationContext,
    ) -> LiquidityAssessment:
        ...


class SlippageModelProtocol(Protocol):
    """Protocol defining the interface for order slippage calculation models."""
    def calculate(
        self,
        order: OrderContract,
        context: ExecutionSimulationContext,
        liquidity: LiquidityAssessment,
    ) -> Decimal:
        ...


class MarketImpactModelProtocol(Protocol):
    """Protocol defining the interface for price impact calculation models."""
    def calculate(
        self,
        order: OrderContract,
        context: ExecutionSimulationContext,
        liquidity: LiquidityAssessment,
    ) -> Decimal:
        ...


class FeeModelProtocol(Protocol):
    """Protocol defining the interface for transaction fee calculation models based on actual fills."""
    def calculate(
        self,
        fills: Tuple[FillContract, ...],
        context: ExecutionSimulationContext,
    ) -> FeeAssessment:
        ...
