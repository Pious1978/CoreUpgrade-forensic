from datetime import datetime, timezone
from decimal import Decimal

from common.clock import Clock
from event_store.memory_store import InMemoryEventStore
from oms.adapters.broker_adapter import BrokerAdapter
from oms.contracts.broker_order_status import BrokerOrderStatus
from oms.contracts.broker_submission_result import BrokerSubmissionResult
from oms.contracts.order_intent import OrderIntentContract, OrderSide, OrderType
from oms.engine.execution_engine import ExecutionEngine
from oms.engine.order_management_engine import OrderManagementEngine
from oms.models.order import Order
from oms.services.order_execution_service import OrderExecutionService
from oms.state_machine.order_state_machine import OrderState
from risk.contracts.risk_check_request import RiskCheckRequest
from risk.engine.pre_trade_risk_engine import PreTradeRiskEngine
from risk.policies.risk_policy import RiskPolicy


class DeterministicClock(Clock):
    """Mock clock for deterministic timeline generation."""
    def __init__(self, start_time: datetime):
        self._current_time = start_time

    def now(self) -> datetime:
        return self._current_time

    def advance(self, seconds: int) -> None:
        from datetime import timedelta
        self._current_time += timedelta(seconds=seconds)


class MockBrokerAdapter(BrokerAdapter):
    """Mock broker adapter to simulate external market behavior."""
    def __init__(self, clock: Clock):
        self._clock = clock
        self.submissions = 0

    def submit_order(self, order: Order) -> BrokerSubmissionResult:
        self.submissions += 1
        return BrokerSubmissionResult(
            broker_order_id=f"EXT-BROKER-{self.submissions}",
            accepted_at=self._clock.now(),
            exchange_order_id=f"EXCH-{self.submissions}X"
        )
        
    def cancel_order(self, order: Order) -> None:
        pass
        
    def get_order_status(self, broker_order_id: str) -> BrokerOrderStatus:
        raise NotImplementedError("Not used in this test harness")


def test_end_to_end_execution_lifecycle():
    # 1. Setup Infrastructure
    clock = DeterministicClock(datetime(2026, 8, 5, 10, 0, 0, tzinfo=timezone.utc))
    store = InMemoryEventStore()
    broker = MockBrokerAdapter(clock)

    # 2. Setup Domain Engines
    policy = RiskPolicy(
        policy_version="v1.0",
        max_position_weight=Decimal("0.20"),
        max_sector_exposure=Decimal("0.40"),
        max_order_value=Decimal("1000000"),
        max_daily_loss=Decimal("0.05"),
        max_portfolio_drawdown=Decimal("0.15"),
        max_liquidity_participation=Decimal("0.10"),
        kill_switch_enabled=False
    )
    risk_engine = PreTradeRiskEngine(policy)
    oms_engine = OrderManagementEngine(risk_engine)
    exec_engine = ExecutionEngine(broker)
    
    # 3. Setup Application Service
    service = OrderExecutionService(oms_engine, exec_engine, store, clock)

    # 4. Create Contracts
    intent = OrderIntentContract(
        intent_id="INTENT-001",
        portfolio_id="PORT-A",
        strategy_id="STRAT-X",
        symbol="NSE:RELIANCE",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("100"),
        price=None,
        currency="INR",
        risk_request_id="RISK-REQ-001",
        execution_trace_id="TRACE-001",
        timestamp=clock.now()
    )

    risk_req = RiskCheckRequest(
        request_id="RISK-REQ-001",
        portfolio_id="PORT-A",
        strategy_id="STRAT-X",
        symbol="NSE:RELIANCE",
        side=OrderSide.BUY,
        quantity=Decimal("100"),
        price=Decimal("2500"),  # Assume current market price for notional
        current_position=Decimal("0"),
        portfolio_value=Decimal("10000000"), # 1 Cr
        daily_pnl=Decimal("0"),
        currency="INR",
        timestamp=clock.now()
    )

    # --- ACTION 1: Submit Intent ---
    snapshot_1 = service.submit_intent(intent, risk_req)
    
    assert snapshot_1.state == OrderState.SUBMITTED
    assert snapshot_1.broker_order_id == "EXT-BROKER-1"
    assert snapshot_1.exchange_order_id == "EXCH-1X"
    assert len(store.read_stream("INTENT-001")) == 2 # AcceptedEvent, SubmittedEvent

    # --- ACTION 2: Broker Webhook (Partial Fill) ---
    clock.advance(5) # 5 seconds later
    partial_status = BrokerOrderStatus(
        broker_order_id="EXT-BROKER-1",
        state=OrderState.PARTIALLY_FILLED,
        filled_quantity=Decimal("40"),
        remaining_quantity=Decimal("60"),
        average_fill_price=Decimal("2501.50")
    )
    
    snapshot_2 = service.process_broker_callback(intent, partial_status)
    
    assert snapshot_2.state == OrderState.PARTIALLY_FILLED
    assert snapshot_2.filled_quantity == Decimal("40")
    assert snapshot_2.remaining_quantity == Decimal("60")
    assert snapshot_2.average_fill_price == Decimal("2501.50")
    assert len(store.read_stream("INTENT-001")) == 3 # + TransitionEvent

    # --- ACTION 3: Broker Webhook (Complete Fill) ---
    clock.advance(2)
    final_status = BrokerOrderStatus(
        broker_order_id="EXT-BROKER-1",
        state=OrderState.FILLED,
        filled_quantity=Decimal("100"),
        remaining_quantity=Decimal("0"),
        average_fill_price=Decimal("2502.00")
    )
    
    snapshot_3 = service.process_broker_callback(intent, final_status)
    
    assert snapshot_3.state == OrderState.FILLED
    assert snapshot_3.is_terminal is True
    assert snapshot_3.filled_quantity == Decimal("100")
    assert snapshot_3.average_fill_price == Decimal("2502.00")
    assert len(store.read_stream("INTENT-001")) == 4 # + Final TransitionEvent

    print("End-to-End Execution Lifecycle completed successfully.")

if __name__ == "__main__":
    test_end_to_end_execution_lifecycle()
