"""
Event Contract Base Class

Represents immutable, point-in-time audit records of past occurrences 
(e.g., ExecutionResult, PromotionDecision) that are born complete in a terminal state 
and explicitly disallow post-creation workflow transitions or trust promotions.
"""

from dataclasses import dataclass
from contracts.base_contract import BaseContract
from contracts.exceptions import ContractValidationError


@dataclass(frozen=True)
class EventContract(BaseContract):
    """
    Base class for immutable event contracts. Disables workflow state mutations 
    and trust escalations since event records are born final and complete.
    """

    def transition_state(self, target_state: Any, actor: str, reason: str) -> BaseContract:
        raise ContractValidationError(
            f"Immutability violation: Event contract '{self.contract_type}' is an immutable record and cannot undergo state transitions."
        )

    def promote_trust(self, target_trust: Any, actor: str, reason: str) -> BaseContract:
        raise ContractValidationError(
            f"Immutability violation: Event contract '{self.contract_type}' has a fixed genesis trust tier and cannot be promoted."
        )
