from typing import Optional
from decimal import Decimal

from common.clock import Clock
from event_store.memory_store import InMemoryEventStore
from event_store.store_protocol import EventStore
from oms.adapters.broker_adapter import BrokerAdapter
from oms.engine.execution_engine import ExecutionEngine
from oms.engine.order_management_engine import OrderManagementEngine
from oms.services.order_execution_service import OrderExecutionService
from risk.engine.pre_trade_risk_engine import PreTradeRiskEngine
from risk.policies.risk_policy import RiskPolicy


def create_order_execution_service(
    risk_policy: Optional[RiskPolicy] = None,
    broker_adapter: Optional[BrokerAdapter] = None,
    event_store: Optional[EventStore] = None,
    clock: Optional[Clock] = None,
) -> OrderExecutionService:
    """
    Composition root factory for the canonical OMS execution spine.

    Wiring hierarchy:
        RiskPolicy -> PreTradeRiskEngine
        PreTradeRiskEngine -> OrderManagementEngine
        BrokerAdapter -> ExecutionEngine
        EventStore + Clock + OMS + Execution -> OrderExecutionService
    """
    # 1. Risk Policy & Engine
    if risk_policy is None:
        risk_policy = RiskPolicy(
            policy_version="v1.0.0",
            max_position_weight=Decimal("1.0"),
            max_sector_exposure=Decimal("1.0"),
            max_order_value=Decimal("1000000.0"),
            max_daily_loss=Decimal("0.05"),
            max_portfolio_drawdown=Decimal("0.15"),
            max_liquidity_participation=Decimal("1.0"),
            kill_switch_enabled=False,
        )
    risk_engine = PreTradeRiskEngine(risk_policy)

    # 2. OMS & Execution Engines
    oms_engine = OrderManagementEngine(risk_engine=risk_engine)

    if broker_adapter is None:
        raise ValueError("broker_adapter must be provided to compose the execution engine.")

    exec_engine = ExecutionEngine(broker_adapter=broker_adapter)

    # 3. Store & Clock Defaults
    if event_store is None:
        event_store = InMemoryEventStore()

    if clock is None:
        from datetime import datetime, timezone
        class DefaultSystemClock:
            def now(self) -> datetime:
                return datetime.now(timezone.utc)
        clock = DefaultSystemClock() # type: ignore

    # 4. Outer Application Service
    return OrderExecutionService(
        oms_engine=oms_engine,
        execution_engine=exec_engine,
        event_store=event_store,
        clock=clock,
    )
