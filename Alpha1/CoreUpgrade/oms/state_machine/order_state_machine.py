from enum import Enum
from types import MappingProxyType
from typing import Final


class OrderState(str, Enum):
    NEW = "NEW"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class OrderStateMachine:
    """Enforces valid state transitions and lifecycle rules using an optimized,
    immutable dictionary-based adjacency mapping and frozenset target lookups.
    """

    _ALLOWED_TRANSITIONS: Final[MappingProxyType[OrderState, frozenset[OrderState]]] = MappingProxyType({
        OrderState.NEW: frozenset({
            OrderState.SUBMITTED,
            OrderState.REJECTED,
        }),
        OrderState.SUBMITTED: frozenset({
            OrderState.ACKNOWLEDGED,
            OrderState.REJECTED,
        }),
        OrderState.ACKNOWLEDGED: frozenset({
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.CANCELLED,
        }),
        OrderState.PARTIALLY_FILLED: frozenset({
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.CANCELLED,
        }),
    })

    _TERMINAL_STATES: Final[frozenset[OrderState]] = frozenset({
        OrderState.FILLED,
        OrderState.CANCELLED,
        OrderState.REJECTED,
    })

    def __init__(self, initial_state: OrderState = OrderState.NEW) -> None:
        if not isinstance(initial_state, OrderState):
            raise TypeError(f"initial_state must be OrderState, got {type(initial_state)}")
        self._current_state = initial_state

    @property
    def current_state(self) -> OrderState:
        return self._current_state

    @property
    def is_terminal(self) -> bool:
        """Indicates whether the order has reached a final terminal state."""
        return self._current_state in self._TERMINAL_STATES

    def can_transition(self, target_state: OrderState) -> bool:
        """Evaluates whether a transition to the target state is legally permitted."""
        if not isinstance(target_state, OrderState):
            return False
        allowed_targets = self._ALLOWED_TRANSITIONS.get(self._current_state, frozenset())
        return target_state in allowed_targets

    def transition(self, target_state: OrderState) -> None:
        """Transitions the order state if permitted.

        Raises:
            TypeError: If target_state is not an OrderState.
            ValueError: If the state transition is illegal.
        """
        if not isinstance(target_state, OrderState):
            raise TypeError(f"target_state must be OrderState, got {type(target_state)}")

        if not self.can_transition(target_state):
            raise ValueError(
                f"Invalid order state transition from {self._current_state.value} to {target_state.value}"
            )

        self._current_state = target_state
