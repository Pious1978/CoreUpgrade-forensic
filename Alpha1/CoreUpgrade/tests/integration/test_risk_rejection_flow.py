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
    def __init__(self, timestamp: datetime):
        self._timestamp = timestamp

    def now(self) -> datetime:
        return self._timestamp


class MockBrokerAdapter(BrokerAdapter):
    """Broker spy. If risk boundary fails, submissions will reveal it."""
    def __init__(self):
        self.submissions = 0

    def submit_order(self, order: Order) -> BrokerSubmissionResult:
        self.submissions += 1
        raise AssertionError("Broker must never receive risk-rejected orders")

    def cancel_order(self, order: Order):
        pass

    def get_order_status(self, broker_order_id: str) -> BrokerOrderStatus:
        raise NotImplementedError


def test_risk_rejection_flow():
    # -------------------------
    # Infrastructure
    # -------------------------
    clock = DeterministicClock(datetime(2026, 8, 5, 10, 0, 0, tzinfo=timezone.utc))
    store = InMemoryEventStore()
    broker = MockBrokerAdapter()

    # -------------------------
    # Risk Policy
    # -------------------------
    policy = RiskPolicy(
        policy_version="v1.0",
        max_position_weight=Decimal("0.05"),
        max_sector_exposure=Decimal("0.20"),
        max_order_value=Decimal("100000"),
        max_daily_loss=Decimal("0.05"), # Hardened to positive magnitude fraction
        max_portfolio_drawdown=Decimal("0.15"), # Hardened to positive magnitude fraction
        max_liquidity_participation=Decimal("0.10"),
        kill_switch_enabled=False
    )
    
    risk_engine = PreTradeRiskEngine(policy)
    oms_engine = OrderManagementEngine(risk_engine)
    execution_engine = ExecutionEngine(broker)
    service = OrderExecutionService(oms_engine, execution_engine, store, clock)

    # -------------------------
    # Intent & Risk Request
    # -------------------------
    intent = OrderIntentContract(
        intent_id="INTENT-RISK-001",
        portfolio_id="PORT-A",
        strategy_id="STRATEGY-X",
        symbol="NSE:RELIANCE",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1000"),
        price=None,
        currency="INR",
        risk_request_id="RISK-001",
        execution_trace_id="TRACE-RISK-001",
        timestamp=clock.now()
    )

    risk_request = RiskCheckRequest(
        request_id="RISK-001",
        portfolio_id="PORT-A",
        strategy_id="STRATEGY-X",
        symbol="NSE:RELIANCE",
        side=OrderSide.BUY,
        quantity=Decimal("1000"),
        price=Decimal("2500"),
        current_position=Decimal("0"),
        portfolio_value=Decimal("1000000"), # Portfolio only 10 lakh
        daily_pnl=Decimal("0"),
        currency="INR",                     # Added currency to satisfy VSC 7 contract
        timestamp=clock.now()
    )

    # -------------------------
    # Execute
    # -------------------------
    snapshot = service.submit_intent(intent, risk_request)

    # -------------------------
    # Assertions
    # -------------------------
    stream = store.read_stream("INTENT-RISK-001")

    # Risk rejection must exist and be the ONLY event
    assert len(stream) == 1
    event = stream[0]
    assert event.__class__.__name__ == "RiskRejectedEvent"
    assert "Policy Violations" in event.reason

    # Snapshot must rebuild correctly
    assert snapshot.state == OrderState.REJECTED
    assert "RISK_ENGINE Rejection" in snapshot.latest_error

    # No broker crossing
    assert broker.submissions == 0
    print("Risk rejection lifecycle completed successfully.")

if __name__ == "__main__":
    test_risk_rejection_flow()
