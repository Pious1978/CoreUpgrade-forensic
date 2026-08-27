from contracts.broker.order_contract import OrderContract
from contracts.broker.broker_response_contract import BrokerResponseContract
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class ExecutionReconciliationContract:
    order_id: str
    planned_quantity: Decimal
    filled_quantity: Decimal
    remaining_quantity: Decimal
    slippage: Decimal
    slippage_percentage: Decimal
    status: str
    correlation_id: str
    broker_name: str

    def __post_init__(self):
        if self.filled_quantity > self.planned_quantity:
            raise ValueError("Reconciliation error: Filled quantity cannot exceed planned order quantity")
        if self.remaining_quantity < 0:
            raise ValueError("Reconciliation error: Remaining quantity cannot be negative")
        if self.filled_quantity < 0:
            raise ValueError("Reconciliation error: Filled quantity cannot be negative")

class ReconciliationEngine:
    """
    Compares internal intent against broker responses to calculate discrepancies,
    partial fills, absolute slippage, and percentage slippage invariants.
    """
    @staticmethod
    def reconcile(order: OrderContract, response: BrokerResponseContract, actual_fill_price: Decimal = None) -> ExecutionReconciliationContract:
        slippage = Decimal("0")
        slippage_percentage = Decimal("0")

        if order.limit_price and actual_fill_price and order.limit_price > 0:
            if order.side.value == "BUY":
                slippage = actual_fill_price - order.limit_price
            else:
                slippage = order.limit_price - actual_fill_price
            
            slippage_percentage = (slippage / order.limit_price) * Decimal("100")

        return ExecutionReconciliationContract(
            order_id=order.order_id,
            planned_quantity=order.quantity,
            filled_quantity=response.filled_quantity,
            remaining_quantity=response.remaining_quantity,
            slippage=slippage,
            slippage_percentage=slippage_percentage.quantize(Decimal("0.0001")),
            status=response.status.value,
            correlation_id=order.correlation_id,
            broker_name=order.broker_name
        )
