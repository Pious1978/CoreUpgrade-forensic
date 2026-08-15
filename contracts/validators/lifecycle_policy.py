"""
Lifecycle Policy Validator

Enforces cross-dimensional consistency between the State Machine and Trust Machine, 
ensuring sensitive lifecycle states are gated by appropriate trust tiers.
"""

from typing import Dict, FrozenSet
from contracts.state import ContractState
from contracts.trust import TrustLevel
from contracts.exceptions import ContractValidationError

ALLOWED_STATE_TRUST_COMBINATIONS: Dict[ContractState, FrozenSet[TrustLevel]] = {
    ContractState.CREATED: frozenset({
        TrustLevel.UNVERIFIED,
        TrustLevel.VERIFIED,
    }),
    ContractState.VALIDATED: frozenset({
        TrustLevel.VERIFIED,
        TrustLevel.GOVERNANCE_CERTIFIED,
    }),
    ContractState.GOVERNANCE_APPROVED: frozenset({
        TrustLevel.GOVERNANCE_CERTIFIED,
    }),
    ContractState.PORTFOLIO_ELIGIBLE: frozenset({
        TrustLevel.GOVERNANCE_CERTIFIED,
        TrustLevel.EXECUTION_AUTHORIZED,
    }),
    ContractState.EXECUTED: frozenset({
        TrustLevel.EXECUTION_AUTHORIZED,
    }),
    ContractState.REJECTED: frozenset(TrustLevel),  # Rejection is permitted from any trust tier
}


def validate_state_trust_combination(state: ContractState, trust: TrustLevel) -> None:
    """
    Validates whether the current state and trust level combination is legally permitted.
    Raises ContractValidationError if the combination violates governance policy.
    """
    resolved_state = ContractState(state)
    resolved_trust = TrustLevel(trust)

    allowed_trusts = ALLOWED_STATE_TRUST_COMBINATIONS.get(resolved_state, frozenset())
    if resolved_trust not in allowed_trusts:
        raise ContractValidationError(
            f"Lifecycle policy violation: state '{resolved_state.value}' cannot coexist with trust level '{resolved_trust.value}'."
        )
