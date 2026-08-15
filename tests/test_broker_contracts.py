import pytest
from dataclasses import FrozenInstanceError
from decimal import Decimal

from contracts.broker.order_contract import OrderContract


def test_order_contract_immutability():
    order = OrderContract(
        order_id="ORD-1001",
        portfolio_id="PORT-A",
        symbol="RELIANCE",
        side="BUY",
        quantity=Decimal("100"),
        order_type="LIMIT",
        limit_price=Decimal("2500.00"),
        timestamp=1717171717000,
        strategy_id="STRAT-ALPHA",
        decision_hash="abc123hash",
        correlation_id="RUN-20260803-00001",
        broker_name="PAPER",
    )

    # Verify immutability constraint holds
    with pytest.raises(FrozenInstanceError):
        order.quantity = Decimal("200")