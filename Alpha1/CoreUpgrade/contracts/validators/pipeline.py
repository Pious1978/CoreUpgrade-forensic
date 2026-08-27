"""
Validation Pipeline

Orchestrates execution of the contract validation pipeline (Identity -> Schema -> Lineage -> Lifecycle Policy -> Integrity) 
under configurable ValidationModes.
"""

from enum import Enum
from typing import Any
from contracts.validators.identity import validate_contract_identity
from contracts.validators.schema import validate_contract_schema
from contracts.validators.lineage import (
    validate_state_history_sequence,
    validate_trust_history_sequence,
)
from contracts.validators.lifecycle_policy import validate_state_trust_combination
from contracts.validators.integrity import validate_contract_integrity


class ValidationMode(str, Enum):
    STRICT = "strict"      # Runs complete suite including lifecycle policy and integrity hashing
    FAST = "fast"          # Runs baseline schema, lineage, and lifecycle checks, skips heavy integrity hashing
    NONE = "none"          # Bypasses validation


class ValidationPipeline:

    @staticmethod
    def run(contract: Any, mode: ValidationMode = ValidationMode.STRICT) -> None:
        resolved_mode = ValidationMode(mode)
        if resolved_mode == ValidationMode.NONE:
            return

        # Core Identity & Schema
        validate_contract_identity(contract)
        validate_contract_schema(contract)

        # Lineage Sequencing
        validate_state_history_sequence(contract.state_history, contract.state)
        validate_trust_history_sequence(contract.trust_history, contract.trust_level)

        # State-Trust Lifecycle Cross-Validation Policy (Must run before integrity checks)
        validate_state_trust_combination(contract.state, contract.trust_level)

        if resolved_mode == ValidationMode.STRICT:
            validate_contract_integrity(contract)
