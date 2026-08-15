from dataclasses import dataclass
from typing import Protocol, Tuple
import hashlib
import json

from validation.contracts.strategy_definition import StrategyDefinition
from validation.contracts.validation_result import ValidationResult, CertificationStatus, Violation, Severity
from validation.validators.lookahead_validator import LookAheadValidator

class GovernanceValidatorProtocol(Protocol):
    def validate(self, strategy: StrategyDefinition) -> tuple[Violation, ...]:
        ...

@dataclass(frozen=True, slots=True)
class CertificationEngine:
    """
    Core governance engine bound to the central validator registry, 
    generating cryptographic deterministic trace IDs and enforcing structural certification.
    """
    validators: tuple[GovernanceValidatorProtocol, ...]

    @classmethod
    def default(cls) -> "CertificationEngine":
        """
        Factory method instantiating the certification engine using the production registry.
        Prevents test-only bypasses.
        """
        return cls(
            validators=(
                LookAheadValidator(),
            )
        )

    def certify(self, strategy: StrategyDefinition) -> ValidationResult:
        all_violations = []
        for validator in self.validators:
            violations = validator.validate(strategy)
            all_violations.extend(violations)

        violations_tuple = tuple(all_violations)
        status = CertificationStatus.REJECTED if violations_tuple else CertificationStatus.CERTIFIED

        # Cryptographic deterministic trace ID derivation: SHA256(strategy_id + strategy_hash + validator_list)
        hasher = hashlib.sha256()
        hasher.update(strategy.strategy_id.encode("utf-8"))
        hasher.update(json.dumps(str(strategy.indicators), sort_keys=True).encode("utf-8"))
        for v in self.validators:
            hasher.update(v.__class__.__name__.encode("utf-8"))
        
        trace_id = f"TRACE-{hasher.hexdigest()[:16]}"

        return ValidationResult(
            test_id=strategy.strategy_id,
            status=status,
            violations=violations_tuple,
            execution_trace_id=trace_id,
        )
