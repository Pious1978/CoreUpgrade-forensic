from decimal import Decimal
from .contracts import FillContract, ExecutionOutcome

class OrderMatcher:
    def evaluate(self, order, market_price: Decimal, current_position, available_liquidity: Decimal, latency_ms: int, timestamp: int) -> ExecutionOutcome:
        market_price = Decimal(str(market_price))

        if order.side == OrderSide.SELL:
            if not current_position or current_position.quantity < order.quantity:
                return ExecutionOutcome(
                    status=OrderStatus.REJECTED,
                    fills=(),
                    reports=(),
                    remaining_quantity=order.quantity,
                    error_message="Insufficient position for SELL",
                    latency_ms=latency_ms,
                    market_price=market_price,
                    slippage=Decimal("0"),
                    fees=Decimal("0"),
                    execution_timestamp=timestamp,
                    execution_latency=latency_ms,
                    matching_algorithm="OrderMatcher",
                    session_state="REGULAR",
                    liquidity_snapshot=available_liquidity
                )

        filled_qty = min(order.quantity, available_liquidity)
        remaining_qty = order.quantity - filled_qty

        if order.order_type == OrderType.MARKET or not order.limit_price:
            fill_price = market_price
        else:
            limit_price = Decimal(str(order.limit_price))
            if order.side == OrderSide.BUY:
                if market_price <= limit_price:
                    fill_price = limit_price
                else:
                    return ExecutionOutcome(
                        status=OrderStatus.OPEN,
                        fills=(),
                        reports=(),
                        remaining_quantity=order.quantity,
                        error_message=None,
                        latency_ms=latency_ms,
                        market_price=market_price,
                        slippage=Decimal("0"),
                        fees=Decimal("0"),
                        execution_timestamp=timestamp,
                        execution_latency=latency_ms,
                        matching_algorithm="OrderMatcher",
                        session_state="REGULAR",
                        liquidity_snapshot=available_liquidity
                    )
            elif order.side == OrderSide.SELL:
                if market_price >= limit_price:
                    fill_price = limit_price
                else:
                    return ExecutionOutcome(
                        status=OrderStatus.OPEN,
                        fills=(),
                        reports=(),
                        remaining_quantity=order.quantity,
                        error_message=None,
                        latency_ms=latency_ms,
                        market_price=market_price,
                        slippage=Decimal("0"),
                        fees=Decimal("0"),
                        execution_timestamp=timestamp,
                        execution_latency=latency_ms,
                        matching_algorithm="OrderMatcher",
                        session_state="REGULAR",
                        liquidity_snapshot=available_liquidity
                    )

        status = OrderStatus.FILLED if remaining_qty == 0 else OrderStatus.PARTIAL
        fills = ()
        if filled_qty > 0:
            fill = FillContract(
                execution_id=f"FILL-{timestamp}",
                quantity=filled_qty,
                price=fill_price,
                fee=Decimal("0.0"),
                exchange_timestamp=timestamp,
                broker_timestamp=timestamp,
                liquidity_flag="TAKER",
                venue="PAPER_EXCHANGE",
                trade_id=f"TRD-{timestamp}"
            )
            fills = (fill,)

        return ExecutionOutcome(
            status=status,
            fills=fills,
            reports=(),
            remaining_quantity=remaining_qty,
            error_message=None,
            latency_ms=latency_ms,
            market_price=market_price,
            slippage=Decimal("0"),
            fees=Decimal("0"),
            execution_timestamp=timestamp,
            execution_latency=latency_ms,
            matching_algorithm="OrderMatcher",
            session_state="REGULAR",
            liquidity_snapshot=available_liquidity
        )
