"""
State Machine

Enforces strict sequential lifecycle transitions across platform contracts.
"""

from typing import Set, Dict
from contracts.state import ContractState
from contracts.exceptions import ContractValidationError

ALLOWED_TRANSITIONS: Dict[ContractState, Set[ContractState]] = {
    ContractState.CREATED: {
        ContractState.VALIDATED,
        ContractState.REJECTED,
    },
    ContractState.VALIDATED: {
        ContractState.GOVERNANCE_APPROVED,
        ContractState.REJECTED,
    },
    ContractState.GOVERNANCE_APPROVED: {
        ContractState.PORTFOLIO_ELIGIBLE,
        ContractState.REJECTED,
    },
    ContractState.PORTFOLIO_ELIGIBLE: {
        ContractState.EXECUTED,
        ContractState.REJECTED,
    },
    ContractState.EXECUTED: set(),
    ContractState.REJECTED: set(),
}


def validate_transition(current: ContractState, target: ContractState) -> None:
    curr_state = ContractState(current)
    target_state = ContractState(target)
    if target_state not in ALLOWED_TRANSITIONS.get(curr_state, set()):
        raise ContractValidationError(
            f"Invalid state transition: cannot transition from '{curr_state.value}' to '{target_state.value}'."
        )
