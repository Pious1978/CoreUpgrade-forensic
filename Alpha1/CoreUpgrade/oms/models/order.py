from typing import Iterable, Optional

from oms.contracts.order_intent import OrderIntentContract
from oms.events.order_events import (
    BaseOrderEvent,
    OrderRejectedEvent,
    OrderSubmittedEvent,
    OrderTransitionEvent,
)
from oms.state_machine.order_state_machine import OrderState, OrderStateMachine


class Order:
    """Mutable aggregate root representing an active lifecycle order.
    
    Can be instantiated fresh for new intents, or rehydrated from an event stream
    to process asynchronous commands.
    """

    def __init__(self, intent: OrderIntentContract) -> None:
        if not isinstance(intent, OrderIntentContract):
            raise TypeError(f"intent must be OrderIntentContract, got {type(intent)}")
        self._intent = intent
        self._state_machine = OrderStateMachine()
        self._broker_order_id: Optional[str] = None

    @classmethod
    def rehydrate(cls, intent: OrderIntentContract, events: Iterable[BaseOrderEvent]) -> 'Order':
        """Rebuilds the write-model aggregate strictly from historical facts."""
        order = cls(intent)
        for event in events:
            if isinstance(event, OrderSubmittedEvent):
                order.transition(OrderState.SUBMITTED)
                order._broker_order_id = event.broker_order_id
            elif isinstance(event, OrderTransitionEvent):
                order.transition(event.to_state)
            elif isinstance(event, OrderRejectedEvent):
                order.transition(OrderState.REJECTED)
            # OrderExecutionErrorEvent does not mutate internal lifecycle state
        return order

    @property
    def intent(self) -> OrderIntentContract:
        return self._intent

    @property
    def state(self) -> OrderState:
        return self._state_machine.current_state

    @property
    def is_terminal(self) -> bool:
        return self._state_machine.is_terminal

    @property
    def broker_order_id(self) -> Optional[str]:
        return self._broker_order_id

    def can_transition(self, target_state: OrderState) -> bool:
        return self._state_machine.can_transition(target_state)

    def transition(self, target_state: OrderState) -> None:
        self._state_machine.transition(target_state)

    def set_broker_order_id(self, broker_id: str) -> None:
        if not isinstance(broker_id, str) or not broker_id.strip():
            raise ValueError("broker_id must be a non-empty string")
        if self._broker_order_id is not None:
            raise ValueError("broker_order_id is already set and cannot be mutated")
        self._broker_order_id = broker_id
