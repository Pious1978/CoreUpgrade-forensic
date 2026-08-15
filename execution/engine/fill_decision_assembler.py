from dataclasses import dataclass
from decimal import Decimal
from typing import Tuple

from execution.contracts.fill_contract import FillContract
from execution.contracts.fill_decision_contract import FillDecisionContract, ExecutionStatus
from execution.contracts.order_contract import OrderContract
from execution.models.contracts.fee_assessment import FeeAssessment

@dataclass(frozen=True, slots=True)
class FillDecisionAssembler:
    """
    Assembler component responsible for unifying order intent, execution tranches, 
    and fee assessments into an immutable FillDecisionContract.
    """

    def assemble(
        self,
        order: OrderContract,
        fills: tuple[FillContract, ...],
        fee_assessment: FeeAssessment,
    ) -> FillDecisionContract:
        """
        Computes final filled/remaining quantities, average prices, and constructs the aggregate decision.
        """
        filled_quantity = sum((fill.quantity for fill in fills), Decimal("0"))
        remaining_quantity = order.quantity - filled_quantity

        if filled_quantity == Decimal("0"):
            status = ExecutionStatus.REJECTED
            average_price = Decimal("0")
        elif filled_quantity < order.quantity:
            status = ExecutionStatus.PARTIALLY_FILLED
            notional_sum = sum((fill.notional_value for fill in fills), Decimal("0"))
            average_price = notional_sum / filled_quantity
        else:
            status = ExecutionStatus.FILLED
            notional_sum = sum((fill.notional_value for fill in fills), Decimal("0"))
            average_price = notional_sum / filled_quantity

        return FillDecisionContract(
            status=status,
            requested_quantity=order.quantity,
            filled_quantity=filled_quantity,
            remaining_quantity=remaining_quantity,
            average_price=average_price,
            fills=fills,
            fees=fee_assessment.total_fee,
        )
