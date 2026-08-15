# execution/oms/order_manager.py

import dataclasses
from decimal import Decimal
from typing import Dict, List, Set
from datetime import datetime

from execution.contracts.order_contract import OrderIntent
from execution.contracts.execution_event import ExecutionEvent
from execution.contracts.order_event_record import OrderEventRecord
from execution.oms.order_state_machine import OrderState, OrderStateMachine
from execution.certification.theorem_event_order_consistency_001 import (
    EventOrderConsistencyTheorem,
)
from execution.certification.theorem_order_state_transition_001 import (
    OrderStateTransitionTheorem,
)


@dataclasses.dataclass(frozen=True)
class OrderRecord:
    order_id: str
    intent_id: str
    portfolio_id: str
    instrument_id: str
    side: str
    quantity: Decimal
    order_type: str
    limit_price: Decimal | None
    exchange: str
    state: OrderState
    filled_quantity: Decimal
    average_fill_price: Decimal | None


class OrderManager:
    """
    Manages the mechanical lifecycle of orders.

    Enforces:
    - lineage verification
    - state machine bounds
    - event idempotency
    - fill quantity limits
    - immutable audit history

    Strictly forbids decision-making or unauthorized exposure generation.
    """

    def __init__(self):
        self._orders: Dict[str, OrderRecord] = {}
        self._audit_log: List[OrderEventRecord] = []
        self._processed_events: Set[str] = set()

    def create_order(self, intent: OrderIntent) -> OrderRecord:
        if intent.order_id in self._orders:
            raise ValueError(f"Order ID {intent.order_id} already exists in OMS.")

        record = OrderRecord(
            order_id=intent.order_id,
            intent_id=intent.intent_id,
            portfolio_id=intent.portfolio_id,
            instrument_id=intent.instrument_id,
            side=intent.side,
            quantity=intent.quantity,
            order_type=intent.order_type,
            limit_price=intent.limit_price,
            exchange=intent.exchange,
            state=OrderState.CREATED,
            filled_quantity=Decimal("0"),
            average_fill_price=None,
        )

        self._orders[intent.order_id] = record
        return record

    def get_order(self, order_id: str) -> OrderRecord:
        if order_id not in self._orders:
            raise KeyError(f"Order ID {order_id} not found in OMS.")

        return self._orders[order_id]

    def handle_event(
        self,
        event: ExecutionEvent,
        current_time: datetime,
    ) -> OrderRecord:

        # 1. Idempotency
        if event.event_id in self._processed_events:
            raise ValueError(
                f"Duplicate execution event detected: {event.event_id}"
            )

        record = self.get_order(event.order_id)

        # 2. Lineage consistency
        consistency = EventOrderConsistencyTheorem.verify(
            event,
            record.order_id,
            record.intent_id,
        )

        if not consistency["certified"]:
            raise ValueError(
                f"OMS Lineage Violation: {consistency['reason']}"
            )

        # 3. Determine target state
        target_state = self._map_event_to_target_state(event.event_type)

        # 4. Validate state transition
        transition = OrderStateTransitionTheorem.verify(
            record.state,
            target_state,
        )

        if not transition["certified"]:
            raise ValueError(
                f"OMS State Transition Violation: {transition['reason']}"
            )

        # 5. Calculate fill state
        new_filled_qty = record.filled_quantity
        new_avg_price = record.average_fill_price

        if event.fill_quantity is not None:
            if event.fill_price is None:
                raise ValueError(
                    f"Execution event {event.event_id} contains fill quantity "
                    "without a fill price."
                )

            if event.fill_quantity <= Decimal("0"):
                raise ValueError(
                    f"Execution event {event.event_id} contains "
                    "non-positive fill quantity."
                )

            total_cost = (
                record.filled_quantity
                * (record.average_fill_price or Decimal("0"))
            ) + (
                event.fill_quantity * event.fill_price
            )

            new_filled_qty = (
                record.filled_quantity + event.fill_quantity
            )

            # Fill boundary protection
            if new_filled_qty > record.quantity:
                raise ValueError(
                    f"Fill Boundary Violation: Processing event "
                    f"{event.event_id} would result in a total fill of "
                    f"{new_filled_qty}, exceeding authorized order quantity "
                    f"{record.quantity}."
                )

            new_avg_price = (
                total_cost / new_filled_qty
                if new_filled_qty > Decimal("0")
                else None
            )

        # 6. Atomic state update
        updated_record = dataclasses.replace(
            record,
            state=target_state,
            filled_quantity=new_filled_qty,
            average_fill_price=new_avg_price,
        )

        self._orders[record.order_id] = updated_record

        # 7. Immutable audit record
        audit_record = OrderEventRecord(
            event_id=event.event_id,
            order_id=record.order_id,
            previous_state=record.state,
            new_state=target_state,
            timestamp=current_time,
            event_hash=event.event_hash,
        )

        self._audit_log.append(audit_record)
        self._processed_events.add(event.event_id)

        return updated_record

    def _map_event_to_target_state(
        self,
        event_type: str,
    ) -> OrderState:

        mapping = {
            "ORDER_SUBMITTED": OrderState.SUBMITTED,
            "ORDER_ACCEPTED": OrderState.ACKNOWLEDGED,
            "PARTIAL_FILL": OrderState.PARTIALLY_FILLED,
            "FULL_FILL": OrderState.FILLED,
            "ORDER_REJECTED": OrderState.REJECTED,
            "CANCEL_REQUESTED": OrderState.CANCEL_PENDING,
            "CANCEL_CONFIRMED": OrderState.CANCELLED,
        }

        if event_type not in mapping:
            raise KeyError(
                f"Unknown ExecutionEvent type: {event_type}"
            )

        return mapping[event_type]