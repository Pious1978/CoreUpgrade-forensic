"""
Lifecycle Transition Service

Performs atomic state and trust escalations, validating lifecycle policies, 
appending immutable dual-history logs, and re-finalizing cryptographic hashes.
"""

from datetime import datetime, timezone
from typing import Any
from contracts.base_contract import BaseContract
from contracts.state import ContractState
from contracts.trust import TrustLevel
from contracts.state_machine import validate_transition
from contracts.trust_machine import validate_trust_transition
from contracts.validators.lifecycle_policy import validate_state_trust_combination
from contracts.rebuilder import ContractRebuilder


class LifecycleTransitionService:

    @staticmethod
    def promote(
        contract: BaseContract,
        target_state: ContractState,
        target_trust: TrustLevel,
        actor: str,
        reason: str,
    ) -> BaseContract:
        """
        Atomically promotes a contract to a new state and trust tier, 
        validating state machines, trust machines, and cross-dimensional lifecycle policies.
        """
        curr_state = ContractState(contract.state)
        curr_trust = TrustLevel(contract.trust_level)
        
        target_s = ContractState(target_state)
        target_t = TrustLevel(target_trust)

        # 1. Validate individual machines
        if curr_state != target_s:
            validate_transition(curr_state, target_s)
        if curr_trust != target_t:
            validate_trust_transition(curr_trust, target_t)

        # 2. Validate cross-dimensional policy combination
        validate_state_trust_combination(target_s, target_t)

        now_str = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        actor_str = actor.strip()
        reason_str = reason.strip()

        # 3. Append state history if changed
        updated_s_history = list(contract.state_history)
        if curr_state != target_s:
            updated_s_history.append({
                "state": target_s.value,
                "timestamp": now_str,
                "actor": actor_str,
                "reason": reason_str,
            })

        # 4. Append trust history if changed
        updated_t_history = list(contract.trust_history)
        if curr_trust != target_t:
            updated_t_history.append({
                "from": curr_trust.value,
                "to": target_t.value,
                "timestamp": now_str,
                "actor": actor_str,
                "reason": reason_str,
            })

        # 5. Rebuild and re-finalize hash atomically
        updates = {
            "state": target_s,
            "trust_level": target_t,
            "state_history": tuple(updated_s_history),
            "trust_history": tuple(updated_t_history),
            "payload_hash": None,  # Reset for re-hashing
        }

        rebuilt_contract = ContractRebuilder.rebuild(contract, updates)
        rebuilt_contract.finalize()
        return rebuilt_contract
