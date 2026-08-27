import pytest
from dataclasses import FrozenInstanceError
from decimal import Decimal
from contracts.broker.enums import OrderSide, OrderType, OrderStatus
from contracts.broker.order_contract import OrderContract
from execution_gateway.reconciliation_engine import ReconciliationEngine
from contracts.broker.broker_response_contract import BrokerResponseContract

def test_order_contract_validation_and_immutability():
    # Valid order creation
    order = OrderContract(
        order_id="ORD-1001",
        portfolio_id="PORT-A",
        symbol="RELIANCE",
        side=OrderSide.BUY,
        quantity=Decimal("100"),
        order_type=OrderType.LIMIT,
        limit_price=Decimal("2500.00"),
        timestamp=1717171717000,
        strategy_id="STRAT-ALPHA",
        decision_hash="abc123hash",
        correlation_id="RUN-20260803-00001",
        broker_name="PAPER"
    )

    # Immutability check
    with pytest.raises(FrozenInstanceError):
        order.quantity = Decimal("200")

    # Invalid quantity failure check
    with pytest.raises(ValueError):
        OrderContract(
            order_id="ORD-FAIL",
            portfolio_id="PORT-A",
            symbol="RELIANCE",
            side=OrderSide.BUY,
            quantity=Decimal("-10"),
            order_type=OrderType.MARKET,
            limit_price=None,
            timestamp=1,
            strategy_id="TEST",
            decision_hash="HASH",
            correlation_id="RUN-20260803-00001",
            broker_name="PAPER"
        )

def test_reconciliation_slippage_calculation():
    order = OrderContract(
        order_id="ORD-1002",
        portfolio_id="PORT-A",
        symbol="INFY",
        side=OrderSide.BUY,
        quantity=Decimal("50"),
        order_type=OrderType.LIMIT,
        limit_price=Decimal("1500.00"),
        timestamp=1717171717000,
        strategy_id="STRAT-BETA",
        decision_hash="hashXYZ",
        correlation_id="RUN-20260803-00002",
        broker_name="PAPER"
    )

    response = BrokerResponseContract(
        order_id="ORD-1002",
        broker_order_id="BRK-999",
        status=OrderStatus.FILLED,
        filled_quantity=Decimal("50"),
        remaining_quantity=Decimal("0"),
        average_fill_price=Decimal("1502.50"),
        error_message=None,
        timestamp=1717171718000,
        correlation_id="RUN-20260803-00002",
        broker_name="PAPER"
    )

    recon = ReconciliationEngine.reconcile(order, response, actual_fill_price=Decimal("1502.50"))
    
    assert recon.slippage == Decimal("2.50")
    assert recon.status == "FILLED"
    assert recon.correlation_id == "RUN-20260803-00002"
