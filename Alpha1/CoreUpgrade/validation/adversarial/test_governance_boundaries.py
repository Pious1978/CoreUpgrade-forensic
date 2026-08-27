import pytest
from dataclasses import dataclass, field
from typing import List

from validation.validation_engine import CertificationEngine
from validation.adversarial.fixtures.strat_overfit_001 import ADVERSARIAL_FIXTURE
from validation.adversarial.fixtures.valid_ema_001 import ValidEmaFixture
from governance.enforcement.barrier import DownstreamGovernanceEnforcement, CertificationRejectedError

@dataclass
class MockPortfolioManager:
    """Tracks admitted strategies for zero-side-effect verification."""
    admitted_strategies: list[str] = field(default_factory=list)

    def register(self, strategy_id: str) -> None:
        self.admitted_strategies.append(strategy_id)

def test_rejected_strategy_blocked_downstream_with_zero_side_effects() -> None:
    """
    Proves that a REJECTED certification result raises structured exceptions,
    carries programmatic violation codes, and leaves downstream portfolio state completely unmutated.
    """
    engine = CertificationEngine.default()
    fixture = ADVERSARIAL_FIXTURE
    
    # 1. Certify adversarial strategy
    result = engine.certify(fixture.strategy)
    assert result.status == fixture.expected_status

    # 2. Track downstream portfolio state before attempted admission
    portfolio = MockPortfolioManager(admitted_strategies=["EXISTING-STRAT-1"])
    initial_count = len(portfolio.admitted_strategies)

    # 3. Assert downstream admission barrier rejects the artifact using pytest semantics
    enforcement = DownstreamGovernanceEnforcement()

    with pytest.raises(CertificationRejectedError) as exc_info:
        enforcement.admit_strategy(
            strategy_id=fixture.strategy.strategy_id,
            validation_result=result,
            portfolio_admission_hook=portfolio.register,
        )

    # 4. Verify structured exception provenance
    err = exc_info.value
    assert "LOOKAHEAD_BIAS" in err.violation_codes
    assert err.trace_id.startswith("TRACE-")

    # 5. Verify zero side effects on downstream state
    assert len(portfolio.admitted_strategies) == initial_count, (
        "Security Violation: Portfolio state mutated despite governance rejection."
    )
    assert fixture.strategy.strategy_id not in portfolio.admitted_strategies

def test_certified_strategy_successfully_admitted_downstream() -> None:
    """
    Proves the positive admission path: a valid strategy successfully clears 
    certification and registers in downstream portfolio management.
    """
    engine = CertificationEngine.default()
    fixture = ValidEmaFixture()

    # 1. Certify valid strategy
    result = engine.certify(fixture.strategy)
    assert result.status == fixture.expected_status
    assert len(result.violations) == 0

    # 2. Attempt downstream admission
    portfolio = MockPortfolioManager()
    enforcement = DownstreamGovernanceEnforcement()

    enforcement.admit_strategy(
        strategy_id=fixture.strategy.strategy_id,
        validation_result=result,
        portfolio_admission_hook=portfolio.register,
    )

    # 3. Verify successful admission
    assert fixture.strategy.strategy_id in portfolio.admitted_strategies
    assert len(portfolio.admitted_strategies) == 1
