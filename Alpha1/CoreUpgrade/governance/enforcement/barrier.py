from dataclasses import dataclass
from typing import Tuple
from validation.contracts.validation_result import CertificationStatus, ValidationResult

class CertificationRejectedError(Exception):
    """
    Raised when attempting to admit a strategy that failed governance certification.
    Exposes structured programmatic violation codes and trace identifiers.
    """
    def __init__(self, message: str, violation_codes: tuple[str, ...], trace_id: str) -> None:
        super().__init__(message)
        self.violation_codes = violation_codes
        self.trace_id = trace_id

@dataclass(frozen=True, slots=True)
class DownstreamGovernanceEnforcement:
    """
    Pure enforcement barrier protecting downstream portfolio and execution pipelines 
    from uncertified artifacts without mutating input validation outcomes.
    """

    def admit_strategy(
        self, 
        strategy_id: str, 
        validation_result: ValidationResult,
        portfolio_admission_hook: callable = None,
    ) -> None:
        """
        Validates certification status before admitting a strategy. 
        Ensures zero portfolio mutation occurs if certification fails.
        """
        if validation_result.status != CertificationStatus.CERTIFIED:
            codes = tuple(v.code for v in validation_result.violations)
            raise CertificationRejectedError(
                message=(
                    f"Governance Gate Violation: Strategy '{strategy_id}' is rejected "
                    f"([Trace: {validation_result.execution_trace_id}]). "
                    f"Violations: {codes}"
                ),
                violation_codes=codes,
                trace_id=validation_result.execution_trace_id,
            )

        # Execute downstream admission hook only when certification succeeds
        if portfolio_admission_hook is not None:
            portfolio_admission_hook(strategy_id)
