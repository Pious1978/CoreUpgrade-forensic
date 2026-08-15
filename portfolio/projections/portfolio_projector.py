from decimal import Decimal

from oms.contracts.order_intent import OrderSide, OrderIntentContract
from oms.events.base import BaseOrderEvent
from oms.events.execution import TradeFillEvent
from portfolio.exceptions import PortfolioProjectionError
from portfolio.models.portfolio_state import PortfolioState
from portfolio.models.position import Position


class PortfolioProjector:
    """Pure functional projection that translates trade executions into ledger entries."""

    @staticmethod
    def apply(
        state: PortfolioState, 
        intent: OrderIntentContract, 
        event: BaseOrderEvent
    ) -> PortfolioState:
        
        # Bounded Context enforcement: We only care about explicit accounting facts
        if not isinstance(event, TradeFillEvent):
            return state

        # 1. Replay Idempotency Guard
        if event.fill_id in state.applied_fills:
            return state

        # 2. Integrity Guards
        if event.fill_quantity <= Decimal("0"):
            raise PortfolioProjectionError(f"Invalid fill quantity {event.fill_quantity} on {event.fill_id}")

        # 3. Apply Cash (net_cash_change already accounts for gross, fees, and side)
        new_cash = state.cash_balance + event.net_cash_change

        # 4. Apply Position
        position_qty_change = event.fill_quantity if intent.side == OrderSide.BUY else -event.fill_quantity
        
        new_positions = dict(state.positions)
        current_position = new_positions.get(
            intent.symbol, 
            Position(symbol=intent.symbol, quantity=Decimal("0"), average_cost=Decimal("0"))
        )
        
        new_positions[intent.symbol] = current_position.apply_fill(
            fill_qty=position_qty_change, 
            fill_price=event.fill_price
        )

        # 5. Update Replay Metadata
        new_applied_fills = set(state.applied_fills)
        new_applied_fills.add(event.fill_id)

        return PortfolioState(
            portfolio_id=state.portfolio_id,
            cash_balance=new_cash,
            positions=new_positions,
            applied_fills=frozenset(new_applied_fills)
        )
