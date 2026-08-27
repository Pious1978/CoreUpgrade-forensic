from dataclasses import dataclass
from decimal import Decimal
from typing import Tuple
from execution.contracts.fill_contract import FillContract
from execution.simulation.context import ExecutionSimulationContext
from execution.models.contracts.fee_assessment import FeeAssessment

@dataclass(frozen=True, slots=True)
class BaselineFeeModel:
    """
    Baseline transaction fee model computing flat broker commissions 
    and percentage-based exchange/regulatory fees from actual fill tranches.
    """
    flat_fee_per_fill: Decimal = Decimal("0.00")
    exchange_fee_rate: Decimal = Decimal("0.0003")  # 0.03% default exchange fee
    broker_commission_rate: Decimal = Decimal("0.0001")  # 0.01% default broker commission
    regulatory_fee_rate: Decimal = Decimal("0.00002")  # 0.002% default regulatory fee

    def __post_init__(self) -> None:
        if self.flat_fee_per_fill < Decimal("0"):
            raise ValueError("Flat fee per fill cannot be negative.")
        if self.exchange_fee_rate < Decimal("0"):
            raise ValueError("Exchange fee rate cannot be negative.")
        if self.broker_commission_rate < Decimal("0"):
            raise ValueError("Broker commission rate cannot be negative.")
        if self.regulatory_fee_rate < Decimal("0"):
            raise ValueError("Regulatory fee rate cannot be negative.")

    def calculate(
        self,
        fills: Tuple[FillContract, ...],
        context: ExecutionSimulationContext,
    ) -> FeeAssessment:
        """
        Calculates aggregate fee assessments across all atomic fill tranches.
        """
        total_exchange_fee = Decimal("0")
        total_broker_commission = Decimal("0")
        total_regulatory_fee = Decimal("0")
        flat_total = Decimal("0")

        for fill in fills:
            notional = fill.notional_value
            flat_total += self.flat_fee_per_fill
            total_exchange_fee += notional * self.exchange_fee_rate
            total_broker_commission += notional * self.broker_commission_rate
            total_regulatory_fee += notional * self.regulatory_fee_rate

        total_fee = (
            flat_total
            + total_exchange_fee
            + total_broker_commission
            + total_regulatory_fee
        )

        return FeeAssessment(
            total_fee=total_fee,
            exchange_fee=total_exchange_fee + (flat_total / Decimal("3")),  # Distribute flat fee context
            broker_commission=total_broker_commission + (flat_total / Decimal("3")),
            regulatory_fee=total_regulatory_fee + (flat_total / Decimal("3")),
        )
