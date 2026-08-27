from decimal import Decimal
from .contracts import ExecutionOutcome

class ExecutionResultFactory:
    @staticmethod
    def submitted(order, latency_ms: int = 0, timestamp: int = 0) -> ExecutionOutcome:
        return ExecutionOutcome(
            status=OrderStatus.SUBMITTED,
            fills=(),
            reports=(),
            remaining_quantity=order.quantity,
            error_message=None,
            latency_ms=latency_ms,
            market_price=Decimal("0"),
            slippage=Decimal("0"),
            fees=Decimal("0"),
            execution_timestamp=timestamp,
            execution_latency=latency_ms,
            matching_algorithm="Initial",
            session_state="REGULAR",
            liquidity_snapshot=Decimal("0")
        )

    @staticmethod
    def rejected(order, reason: str, latency_ms: int = 0, timestamp: int = 0) -> ExecutionOutcome:
        return ExecutionOutcome(
            status=OrderStatus.REJECTED,
            fills=(),
            reports=(),
            remaining_quantity=order.quantity,
            error_message=reason,
            latency_ms=latency_ms,
            market_price=Decimal("0"),
            slippage=Decimal("0"),
            fees=Decimal("0"),
            execution_timestamp=timestamp,
            execution_latency=latency_ms,
            matching_algorithm="PolicyChain",
            session_state="REGULAR",
            liquidity_snapshot=Decimal("0")
        )

    @staticmethod
    def market_closed(order, reason: str, latency_ms: int = 0, timestamp: int = 0) -> ExecutionOutcome:
        return ExecutionOutcome(
            status=OrderStatus.OPEN,
            fills=(),
            reports=(),
            remaining_quantity=order.quantity,
            error_message=reason,
            latency_ms=latency_ms,
            market_price=Decimal("0"),
            slippage=Decimal("0"),
            fees=Decimal("0"),
            execution_timestamp=timestamp,
            execution_latency=latency_ms,
            matching_algorithm="MarketSession",
            session_state="CLOSED",
            liquidity_snapshot=Decimal("0")
        )
