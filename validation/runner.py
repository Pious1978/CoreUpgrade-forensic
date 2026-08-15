from dataclasses import dataclass
from typing import Protocol, tuple
from validation.contracts.validation_result import ValidationResult, CertificationStatus

class StrategyValidatorProtocol(Protocol):
    """Protocol defining a standalone strategy validation test case."""
    test_id: str
    description: str

    def run(self) -> ValidationResult:
        ...

@dataclass(frozen=True, slots=True)
class ValidationSuiteRunner:
    """
    Executes the permanent validation track, asserting that adversarial strategies 
    fail fast and legitimate strategies achieve certification.
    """
    validators: tuple[StrategyValidatorProtocol, ...]

    def execute_suite(self) -> tuple[ValidationResult, ...]:
        results = []
        for validator in self.validators:
            result = validator.run()
            results.append(result)
            
            # Print empirical validation evidence
            status_symbol = "✅" if result.status == CertificationStatus.CERTIFIED else "❌"
            print(f"[{status_symbol}] {result.test_id}: {result.status.value}")
            for violation in result.violations:
                print(f"    - Violation: {violation}")

        return tuple(results)
