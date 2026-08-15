"""
Trust Machine

Enforces strict monotonic trust escalation rules, prohibiting downgrades or skipped tiers.
"""

from typing import Set, Dict
from contracts.trust import TrustLevel
from contracts.exceptions import ContractValidationError

TRUST_ORDER = [
    TrustLevel.UNVERIFIED,
    TrustLevel.VERIFIED,
    TrustLevel.GOVERNANCE_CERTIFIED,
    TrustLevel.EXECUTION_AUTHORIZED,
]

ALLOWED_TRUST_TRANSITIONS: Dict[TrustLevel, Set[TrustLevel]] = {
    TrustLevel.UNVERIFIED: {TrustLevel.VERIFIED},
    TrustLevel.VERIFIED: {TrustLevel.GOVERNANCE_CERTIFIED},
    TrustLevel.GOVERNANCE_CERTIFIED: {TrustLevel.EXECUTION_AUTHORIZED},
    TrustLevel.EXECUTION_AUTHORIZED: set(),
}


def validate_trust_transition(current: TrustLevel, target: TrustLevel) -> None:
    curr_enum = TrustLevel(current)
    target_enum = TrustLevel(target)

    curr_idx = TRUST_ORDER.index(curr_enum)
    target_idx = TRUST_ORDER.index(target_enum)

    if target_idx < curr_idx:
        raise ContractValidationError(
            f"Trust downgrade prohibited: cannot transition trust level from '{curr_enum.value}' to '{target_enum.value}'."
        )

    if target_enum not in ALLOWED_TRUST_TRANSITIONS.get(curr_enum, set()):
        raise ContractValidationError(
            f"Invalid trust escalation: cannot transition trust level from '{curr_enum.value}' to '{target_enum.value}'."
        )
