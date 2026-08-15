from dataclasses import dataclass
from validation.contracts.strategy_definition import StrategyDefinition, IndicatorExpression
from validation.contracts.validation_result import CertificationStatus

@dataclass(frozen=True, slots=True)
class ValidEmaFixture:
    test_id: str = "VALID-EMA-001"
    description: str = "Legitimate EMA strategy adhering to strict causality invariants"
    strategy: StrategyDefinition = StrategyDefinition(
        strategy_id="VALID-EMA-001",
        name="SafeTrendEMA",
        indicators=(
            # Positive shift (historical data) is valid and does not leak future snapshots
            IndicatorExpression(name="safe_ema", operation="shift", periods=1),
        ),
    )
    expected_status: CertificationStatus = CertificationStatus.CERTIFIED
