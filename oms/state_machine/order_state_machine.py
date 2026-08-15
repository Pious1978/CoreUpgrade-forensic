from enum import Enum


class OrderState(Enum):
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"


class OrderStateMachine:
    """
    Deterministic order lifecycle state machine.

    The public transition API operates on target OrderState values.
    This keeps the aggregate, execution engine, and event rehydrator
    consistent.
    """

    _TRANSITIONS = {
        OrderState.CREATED: {
            OrderState.SUBMITTED,
            OrderState.REJECTED,
        },

        OrderState.SUBMITTED: {
            OrderState.ACKNOWLEDGED,
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.REJECTED,
        },

        OrderState.ACKNOWLEDGED: {
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.REJECTED,
        },

        OrderState.PARTIALLY_FILLED: {
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.REJECTED,
        },

        OrderState.FILLED: set(),
        OrderState.REJECTED: set(),
    }

    _TERMINAL_STATES = {
        OrderState.FILLED,
        OrderState.REJECTED,
    }

    def __init__(self, initial_state: OrderState = OrderState.CREATED):
        if not isinstance(initial_state, OrderState):
            raise TypeError(
                f"initial_state must be OrderState, got {type(initial_state)}"
            )

        self.state = initial_state

    @property
    def current_state(self) -> OrderState:
        return self.state

    @property
    def is_terminal(self) -> bool:
        return self.state in self._TERMINAL_STATES

    def can_transition(self, target_state: OrderState) -> bool:
        """
        Return True if the requested target state is valid from
        the current state.
        """
        if not isinstance(target_state, OrderState):
            return False

        return target_state in self._TRANSITIONS.get(self.state, set())

    def transition(self, target_state: OrderState) -> OrderState:
        """
        Apply a lifecycle transition to the requested target state.

        The transition is deliberately expressed in terms of domain
        states rather than raw broker event strings.
        """
        if not isinstance(target_state, OrderState):
            raise TypeError(
                f"target_state must be OrderState, got {type(target_state)}"
            )

        if not self.can_transition(target_state):
            raise ValueError(
                f"Invalid state transition: Cannot transition "
                f"from {self.state.value} to {target_state.value}"
            )

        self.state = target_state
        return self.state