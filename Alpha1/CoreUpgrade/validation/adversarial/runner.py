from dataclasses import dataclass

from validation.validation_engine import CertificationEngine
from validation.adversarial.fixtures.strat_overfit_001 import (
    ADVERSARIAL_FIXTURE,
)


@dataclass(frozen=True, slots=True)
class AdversarialCertificationRunner:
    """
    Generic runner executing parameterised adversarial fixtures against
    the centralized certification engine.

    Fixture contract:
    AdversarialFixture (immutable dataclass)
    """

    def run_fixture(self, fixture) -> None:
        engine = CertificationEngine.default()

        strategy = fixture.strategy
        result = engine.certify(strategy)

        # ---------------------------------------------------------
        # Certification status assertion
        # ---------------------------------------------------------
        assert result.status == fixture.expected_status, (
            f"Fixture {fixture.test_id} failed: "
            f"Expected status {fixture.expected_status}, "
            f"got {result.status}"
        )

        # ---------------------------------------------------------
        # Violation count assertion
        # ---------------------------------------------------------
        assert len(result.violations) == 1, (
            f"Fixture {fixture.test_id} failed: "
            f"Expected exactly 1 violation, "
            f"got {len(result.violations)}"
        )

        violation = result.violations[0]

        # ---------------------------------------------------------
        # Violation code assertion
        # ---------------------------------------------------------
        assert violation.code == fixture.expected_violation_code, (
            f"Fixture {fixture.test_id} failed: "
            f"Expected violation code "
            f"{fixture.expected_violation_code}, "
            f"got {violation.code}"
        )

        # ---------------------------------------------------------
        # Severity assertion
        # ---------------------------------------------------------
        assert violation.severity == fixture.expected_severity, (
            f"Fixture {fixture.test_id} failed: "
            f"Expected severity "
            f"{fixture.expected_severity}, "
            f"got {violation.severity}"
        )

        # ---------------------------------------------------------
        # Validator identity assertion
        # ---------------------------------------------------------
        assert violation.validator_name == fixture.expected_validator, (
            f"Fixture {fixture.test_id} failed: "
            f"Expected validator "
            f"{fixture.expected_validator}, "
            f"got {violation.validator_name}"
        )

        # ---------------------------------------------------------
        # Trace lineage assertion
        # ---------------------------------------------------------
        assert result.execution_trace_id.startswith("TRACE-"), (
            f"Fixture {fixture.test_id} failed: "
            f"Malformed trace ID "
            f"{result.execution_trace_id}"
        )

        print("=" * 70)
        print("ADVERSARIAL CERTIFICATION SUITE")
        print("=" * 70)
        print(f"TEST        : {fixture.test_id}")
        print(f"STATUS      : {result.status}")
        print(f"TRACE ID    : {result.execution_trace_id}")
        print("-" * 70)
        print("RESULT      : PASSED")

    def run_suite(self) -> None:
        self.run_fixture(ADVERSARIAL_FIXTURE)


if __name__ == "__main__":
    runner = AdversarialCertificationRunner()
    runner.run_suite()