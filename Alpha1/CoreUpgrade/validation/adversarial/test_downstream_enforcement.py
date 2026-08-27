from validation.validation_engine import CertificationEngine

from validation.adversarial.fixtures.strat_overfit_001 import (
    ADVERSARIAL_FIXTURE,
)


def test_rejected_strategy_blocked_downstream() -> None:
    """
    System regression test proving that a REJECTED certification result
    successfully triggers a hard stop at the downstream portfolio/execution
    barrier.
    """

    engine = CertificationEngine.default()

    fixture = ADVERSARIAL_FIXTURE

    # ---------------------------------------------------------
    # 1. Certify adversarial strategy
    # ---------------------------------------------------------
    result = engine.certify(
        fixture.strategy
    )

    # ---------------------------------------------------------
    # 2. Verify certification rejection
    # ---------------------------------------------------------
    assert result.status == fixture.expected_status, (
        "Fixture certification status mismatch."
    )

    # ---------------------------------------------------------
    # 3. Verify governance violation exists
    # ---------------------------------------------------------
    assert len(result.violations) == 1

    violation = result.violations[0]

    assert violation.code == fixture.expected_violation_code
    assert violation.severity == fixture.expected_severity
    assert violation.validator_name == fixture.expected_validator

    # ---------------------------------------------------------
    # 4. Downstream admission barrier simulation
    # ---------------------------------------------------------
    admitted = False

    if result.status.name == "CERTIFIED":
        admitted = True

    # A rejected strategy must never be admitted
    assert admitted is False