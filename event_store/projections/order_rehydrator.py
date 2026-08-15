from decimal import Decimal
from typing import Iterable

from event_store.models.order_snapshot import OrderSnapshot
from oms.contracts.order_intent import OrderIntentContract
from oms.events.base import BaseOrderEvent
from oms.events.order_events import (
    OrderExecutionErrorEvent,
    OrderRejectedEvent,
    OrderSubmittedEvent,
    OrderTransitionEvent,
)
from oms.events.risk import OrderAcceptedEvent, RiskRejectedEvent
from oms.state_machine.order_state_machine import OrderState, OrderStateMachine


class OrderRehydrator:
    """
    Pure functional projection that folds an event stream and an intent
    into a point-in-time state.

    The shared OrderStateMachine is the authoritative lifecycle
    validator during reconstruction.
    """

    @staticmethod
    def rebuild(
        intent: OrderIntentContract,
        events: Iterable[BaseOrderEvent],
    ) -> OrderSnapshot:

        state_machine = OrderStateMachine(
            initial_state=OrderState.CREATED
        )

        broker_order_id = None
        exchange_order_id = None
        filled_qty = Decimal("0")
        remaining_qty = intent.quantity
        avg_price = None
        latest_error = None
        last_updated = None

        for event in events:

            if event.intent_id != intent.intent_id:
                raise ValueError(
                    f"Stream corruption: Event intent_id "
                    f"{event.intent_id} does not match aggregate "
                    f"intent {intent.intent_id}"
                )

            last_updated = event.timestamp

            # -----------------------------------------------------
            # Risk events
            # -----------------------------------------------------
            if isinstance(event, OrderAcceptedEvent):
                # Risk acceptance does not change lifecycle state.
                pass

            elif isinstance(event, RiskRejectedEvent):
                state_machine.transition(
                    OrderState.REJECTED
                )

                latest_error = (
                    f"RISK_ENGINE Rejection: {event.reason}"
                )

            # -----------------------------------------------------
            # Execution events
            # -----------------------------------------------------
            elif isinstance(event, OrderSubmittedEvent):

                state_machine.transition(
                    OrderState.SUBMITTED
                )

                broker_order_id = event.broker_order_id
                exchange_order_id = event.exchange_order_id

            elif isinstance(event, OrderTransitionEvent):

                state_machine.transition(
                    event.to_state
                )

                filled_qty = event.filled_quantity
                remaining_qty = event.remaining_quantity
                avg_price = event.average_fill_price

            elif isinstance(event, OrderRejectedEvent):

                state_machine.transition(
                    OrderState.REJECTED
                )

                latest_error = (
                    f"BROKER Rejection: {event.reason}"
                )

            elif isinstance(event, OrderExecutionErrorEvent):

                latest_error = (
                    f"Execution Error "
                    f"[{event.error_type}]: "
                    f"{event.error_message}"
                )

        return OrderSnapshot(
            intent=intent,
            state=state_machine.current_state,
            broker_order_id=broker_order_id,
            exchange_order_id=exchange_order_id,
            filled_quantity=filled_qty,
            remaining_quantity=remaining_qty,
            average_fill_price=avg_price,
            latest_error=latest_error,
            last_updated_at=last_updated,
        )