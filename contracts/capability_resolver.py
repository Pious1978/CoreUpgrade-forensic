"""
Capability Resolver

Deterministically resolves contract capabilities from trust tiers, 
eliminating permission drift and stored permission redundancies.
"""

from typing import FrozenSet
from contracts.trust import TrustLevel
from contracts.capability import ContractCapability


class CapabilityResolver:
    TRUST_CAPABILITIES = {
        TrustLevel.UNVERIFIED: frozenset(),
        TrustLevel.VERIFIED: frozenset({
            ContractCapability.RESEARCH_READ,
        }),
        TrustLevel.GOVERNANCE_CERTIFIED: frozenset({
            ContractCapability.RESEARCH_READ,
            ContractCapability.GOVERNANCE_READ,
            ContractCapability.PORTFOLIO_ENTRY,
        }),
        TrustLevel.EXECUTION_AUTHORIZED: frozenset({
            ContractCapability.RESEARCH_READ,
            ContractCapability.GOVERNANCE_READ,
            ContractCapability.PORTFOLIO_ENTRY,
            ContractCapability.EXECUTION,
        }),
    }

    @classmethod
    def resolve(cls, trust_level: TrustLevel) -> FrozenSet[ContractCapability]:
        """Resolves the exact immutable set of capabilities granted for a given trust level."""
        resolved_trust = TrustLevel(trust_level)
        return cls.TRUST_CAPABILITIES.get(resolved_trust, frozenset())
