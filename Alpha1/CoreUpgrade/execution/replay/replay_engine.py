# execution/replay/replay_engine.py
"""
Replay Engine

Authority:
    Execution Layer

Purpose:
    Reconstructs expected position and cash states from an immutable sequence 
    of ExecutionEvents and initial OrderIntents via deterministic event sourcing.

Restrictions:
    - Does not interact with brokers
    - Does not mutate the EventStore
    - Purely functional derivation of expected state from event history
"""
from decimal import Decimal
from typing import Sequence, Dict, Mapping, Tuple
from datetime import datetime

from execution.contracts.order_contract import OrderIntent
from execution.contracts.execution_event import ExecutionEvent
from execution.contracts.cash_snapshot import CashSnapshot
from execution.oms.order_manager import OrderManager, OrderRecord
from execution.reconciliation.position_reconciler import PositionSnapshot

class ReplayEngine:
    """
    Deterministic state projection engine that replays an immutable event stream 
    against authorized order intents to produce expected position and cash snapshots.
    """

    def __init__(self, initial_orders: Sequence[OrderIntent]):
        """
        Initializes the replay engine with the baseline authorized order intents.
        """
        self._order_manager = OrderManager()
        for intent in initial_orders:
            self._order_manager.create_order(intent)

    def replay(
        self,
        events: Sequence[ExecutionEvent],
        initial_cash: Decimal = Decimal("0"),
        base_currency: str = "USD"
    ) -> Tuple[Mapping[str, PositionSnapshot], Mapping[str, CashSnapshot]]:
        """
        Replays a chronological sequence of ExecutionEvents through the OrderManager 
        and projects the resulting state into expected PositionSnapshots and CashSnapshots.
        """
        # 1. Replay all events chronologically through the OrderManager
        for event in events:
            self._order_manager.handle_event(event, current_time=event.timestamp)

        # 2. Project OrderRecords into Positions and Cash
        positions: Dict[str, Dict[str, Decimal]] = {} # instrument_id -> {"quantity": qty, "cost": total_cost}
        cash_flow = Decimal("0")

        for order in self._order_manager._orders.values():
            if order.filled_quantity <= Decimal("0"):
                continue

            instrument = order.instrument_id
            fill_qty = order.filled_quantity
            fill_price = order.average_fill_price or Decimal("0")

            if instrument not in positions:
                positions[instrument] = {"quantity": Decimal("0"), "cost": Decimal("0")}

            if order.side == "BUY":
                positions[instrument]["quantity"] += fill_qty
                positions[instrument]["cost"] += fill_qty * fill_price
                cash_flow -= fill_qty * fill_price
            elif order.side == "SELL":
                positions[instrument]["quantity"] -= fill_qty
                positions[instrument]["cost"] -= fill_qty * fill_price
                cash_flow += fill_qty * fill_price

        # 3. Build PositionSnapshots
        position_snapshots: Dict[str, PositionSnapshot] = {}
        for instrument, data in positions.items():
            qty = data["quantity"]
            avg_price = (data["cost"] / qty) if qty != Decimal("0") else Decimal("0")
            position_snapshots[instrument] = PositionSnapshot(
                symbol=instrument,
                quantity=qty,
                average_price=abs(avg_price)
            )

        # 4. Build Canonical CashSnapshots
        total_cash = initial_cash + cash_flow
        cash_snapshots: Dict[str, CashSnapshot] = {
            base_currency: CashSnapshot(
                currency=base_currency,
                available_cash=total_cash,
                settled_cash=total_cash,       # Assuming immediate settlement in baseline replay model
                unsettled_cash=Decimal("0"),
                margin_used=Decimal("0"),
                buying_power=total_cash
            )
        }

        return position_snapshots, cash_snapshots