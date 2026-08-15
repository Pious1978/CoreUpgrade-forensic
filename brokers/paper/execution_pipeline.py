from decimal import Decimal
from .contracts import ExecutionOutcome, MarketSnapshotContract
from .factory import ExecutionResultFactory

class ExecutionPipeline:
    def __init__(self, market_session_engine, latency_engine, liquidity_engine, order_matcher):
        self.market_session_engine = market_session_engine
        self.latency_engine = latency_engine
        self.liquidity_engine = liquidity_engine
        self.order_matcher = order_matcher

    def process(self, order, current_position, market_snapshot: MarketSnapshotContract, clock) -> ExecutionOutcome:
        latency_ms = self.latency_engine.compute_delay()
        execution_timestamp = clock.now_ms()
        
        session_decision = self.market_session_engine.evaluate_session(order)
        if not session_decision.can_execute:
            if session_decision.queue_order:
                return ExecutionResultFactory.market_closed(order, session_decision.reason or "Market Closed", latency_ms, execution_timestamp)
            else:
                return ExecutionResultFactory.rejected(order, session_decision.reason or "Session Rejected", latency_ms, execution_timestamp)

        available_liquidity = self.liquidity_engine.get_available_liquidity(order.symbol, order.quantity)
        return self.order_matcher.evaluate(
            order=order,
            market_price=market_snapshot.last,
            current_position=current_position,
            available_liquidity=available_liquidity,
            latency_ms=latency_ms,
            timestamp=execution_timestamp
        )
