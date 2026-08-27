from dataclasses import dataclass
from decimal import Decimal
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
    exchange_fee_rate: Decimal = Decimal("0.0003")
    broker_commission_rate: Decimal = Decimal("0.0001")
    regulatory_fee_rate: Decimal = Decimal("0.00002")

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
        fills: tuple[FillContract, ...],
        context: ExecutionSimulationContext,
    ) -> FeeAssessment:
        """
        Calculates aggregate fee assessments across all atomic fill tranches,
        preserving true cost attribution.
        """
        if not fills:
            return FeeAssessment(
                total_fee=Decimal("0"),
                exchange_fee=Decimal("0"),
                broker_commission=Decimal("0"),
                regulatory_fee=Decimal("0"),
                flat_fee=Decimal("0"),
            )

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
            exchange_fee=total_exchange_fee,
            broker_commission=total_broker_commission,
            regulatory_fee=total_regulatory_fee,
            flat_fee=flat_total,
        )
