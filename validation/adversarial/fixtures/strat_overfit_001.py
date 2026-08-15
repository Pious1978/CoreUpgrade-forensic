from dataclasses import dataclass

from validation.contracts.strategy_definition import (
    StrategyDefinition,
    IndicatorExpression,
)

from validation.contracts.validation_result import (
    CertificationStatus,
    Severity,
)


@dataclass(frozen=True, slots=True)
class AdversarialFixture:
    test_id: str
    description: str
    strategy: StrategyDefinition
    expected_status: CertificationStatus
    expected_violation_code: str
    expected_severity: Severity
    expected_validator: str


ADVERSARIAL_FIXTURE = AdversarialFixture(
    test_id="STRAT-OVERFIT-001",

    description=(
        "Look-ahead bias detection via structural indicator inspection"
    ),

    strategy=StrategyDefinition(
        strategy_id="STRAT-OVERFIT-001",
        name="FutureLeakingEMA",
        indicators=(
            IndicatorExpression(
                name="faulty_ema",
                operation="shift",
                periods=-1,
            ),
        ),
    ),

    expected_status=CertificationStatus.REJECTED,

    expected_violation_code="LOOKAHEAD_BIAS",

    expected_severity=Severity.ERROR,

    expected_validator="LookAheadValidator",
)