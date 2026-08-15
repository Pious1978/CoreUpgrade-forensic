from datetime import datetime, timezone
from decimal import Decimal
import pytest

from common.clock import Clock
from event_store.memory_store import InMemoryEventStore
from oms.adapters.broker_adapter import BrokerAdapter
from oms.contracts.broker_order_status import BrokerOrderStatus
from oms.contracts.broker_submission_result import BrokerSubmissionResult
from oms.contracts.order_intent import OrderIntentContract, OrderSide, OrderType
from oms.engine.execution_engine import ExecutionEngine
from oms.engine.order_management_engine import OrderManagementEngine
from oms.models.order import Order
from oms.services.order_execution_service import OrderExecutionService, DuplicateIntentError
from oms.state_machine.order_state_machine import OrderState
from risk.contracts.risk_check_request import RiskCheckRequest
from risk.engine.pre_trade_risk_engine import PreTradeRiskEngine
from risk.policies.risk_policy import RiskPolicy


class DeterministicClock(Clock):
    def __init__(self, timestamp: datetime):
        self._timestamp = timestamp
    def now(self) -> datetime:
        return self._timestamp


class CountingBrokerAdapter(BrokerAdapter):
    """Broker spy to track exactly how many times execution crossed the boundary."""
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

    def cancel_order(self, order: Order):
        pass

    def get_order_status(self, broker_order_id: str) -> BrokerOrderStatus:
        raise NotImplementedError


def build_execution_service(broker, store, clock) -> OrderExecutionService:
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
    return OrderExecutionService(oms_engine, exec_engine, store, clock)


def create_valid_intent(clock) -> tuple[OrderIntentContract, RiskCheckRequest]:
    intent = OrderIntentContract(
        intent_id="INTENT-IDEMP-001",
        portfolio_id="PORT-A",
        strategy_id="STRAT-X",
        symbol="NSE:TCS",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("100"),
        price=None,
        currency="INR",
        risk_request_id="RISK-001",
        execution_trace_id="TRACE-001",
        timestamp=clock.now()
    )
    risk_req = RiskCheckRequest(
        request_id="RISK-001",
        portfolio_id="PORT-A",
        strategy_id="STRAT-X",
        symbol="NSE:TCS",
        side=OrderSide.BUY,
        quantity=Decimal("100"),
        price=Decimal("3500"),
        current_position=Decimal("0"),
        portfolio_value=Decimal("10000000"),
        daily_pnl=Decimal("0"),
        currency="INR",
        timestamp=clock.now()
    )
    return intent, risk_req


def test_duplicate_intent_replay_is_blocked():
    # ---------------------------------
    # Infrastructure Setup
    # ---------------------------------
    clock = DeterministicClock(datetime(2026, 8, 5, 10, 0, 0, tzinfo=timezone.utc))
    store = InMemoryEventStore()
    broker = CountingBrokerAdapter(clock)
    service = build_execution_service(broker, store, clock)
    intent, risk_request = create_valid_intent(clock)

    # ---------------------------------
    # First submission (Expected: Success)
    # ---------------------------------
    snapshot = service.submit_intent(intent, risk_request)

    assert snapshot.state == OrderState.SUBMITTED
    assert broker.submissions == 1
    
    initial_stream = store.read_stream(intent.intent_id)
    assert len(initial_stream) == 2  # OrderAcceptedEvent, OrderSubmittedEvent

    # ---------------------------------
    # Replay identical intent (Expected: Blocked)
    # ---------------------------------
    try:
        service.submit_intent(intent, risk_request)
        assert False, "DuplicateIntentError was not raised!"
    except DuplicateIntentError as e:
        print(f"\nCaught expected idempotency error: {e}")

    # ---------------------------------
    # Verify strict boundary integrity
    # ---------------------------------
    assert broker.submissions == 1  # No double execution!
    final_stream = store.read_stream(intent.intent_id)
    assert len(final_stream) == 2   # Event store was not corrupted!

    print("Duplicate intent replay blocked successfully. Boundary integrity proven.")


if __name__ == "__main__":
    test_duplicate_intent_replay_is_blocked()
