from dataclasses import dataclass
from validation.contracts.strategy_definition import StrategyDefinition
from validation.contracts.validation_result import Violation, Severity

@dataclass(frozen=True, slots=True)
class LookAheadValidator:
    """
    Governance validator inspecting indicator expressions for causality violations,
    emitting structured errors with full metadata.
    """
    validator_name: str = "LookAheadValidator"

    def validate(self, strategy: StrategyDefinition) -> tuple[Violation, ...]:
        violations = []
        for ind in strategy.indicators:
            if ind.operation == "shift" and ind.periods < 0:
                violations.append(
                    Violation(
                        code="LOOKAHEAD_BIAS",
                        message=f"Look-ahead bias detected in indicator '{ind.name}': "
                                f"operation '{ind.operation}' uses negative periods ({ind.periods}), accessing future data (t+N).",
                        severity=Severity.ERROR,
                        validator_name=self.validator_name,
                    )
                )
        return tuple(violations)
