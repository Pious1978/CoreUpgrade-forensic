from dataclasses import dataclass, field
from decimal import Decimal

from portfolio.contracts.portfolio_contract import PortfolioContract
from portfolio.contracts.portfolio_certificate import (
    PortfolioCertificate,
    OptimizerIdentity,
    PortfolioExposure,
    TargetWeight,
)
from portfolio.engines.portfolio_constraint_validator import PortfolioConstraintValidator


@dataclass(frozen=True, slots=True)
class PortfolioCertificateIssuer:
    """
    Issues a PortfolioCertificate from a real, validated PortfolioContract.

    Fields genuinely derived from real portfolio state:
        portfolio_id, timestamp, exposure, target_weights, certified

    Fields with no real producer anywhere in this system today, and therefore
    populated with explicit, clearly-labeled placeholders rather than fabricated
    values that would masquerade as real provenance:
        alpha_vector_hash   - no alpha/research signal artifact flows into
                              PortfolioBuilder today
        universe_hash       - no investment-universe definition flows into
                              PortfolioBuilder today
        risk_hash           - no risk-model artifact flows into PortfolioBuilder
                              today (separate from PreTradeRiskEngine, which
                              operates later, at order-authorization time, not
                              at portfolio-construction time)
        optimizer_identity  - PortfolioBuilder performs direct weight-to-quantity
                              conversion, not optimization; there is no optimizer
                              to identify

    constraint_evaluations is left empty: PortfolioConstraintValidator currently
    returns human-readable violation strings, not structured per-constraint
    PASS/FAIL/SOFT_VIOLATION records with observed/limit values. Producing real
    ConstraintEvaluation objects would require extending the validator itself,
    which is a separate, explicit piece of work, not part of this change.
    """

    validator: PortfolioConstraintValidator = field(
        default_factory=PortfolioConstraintValidator
    )

    def issue(self, portfolio_contract: PortfolioContract) -> PortfolioCertificate:
        violations = self.validator.validate(portfolio_contract)

        return PortfolioCertificate(
            portfolio_id=portfolio_contract.portfolio_id,
            timestamp=portfolio_contract.timestamp,
            alpha_vector_hash="NO-ALPHA-PRODUCER-EXISTS",
            universe_hash="NO-UNIVERSE-PRODUCER-EXISTS",
            risk_hash="NO-RISK-MODEL-PRODUCER-EXISTS",
            optimizer_identity=OptimizerIdentity(
                optimizer_id="NO-OPTIMIZER-PRODUCER-EXISTS",
                version="N/A",
                implementation_hash="N/A",
            ),
            exposure=PortfolioExposure(
                invested_weight=Decimal("1") - portfolio_contract.cash_weight,
                cash_weight=portfolio_contract.cash_weight,
            ),
            target_weights=tuple(
                TargetWeight(instrument_id=t.symbol, weight=t.target_weight)
                for t in portfolio_contract.targets
            ),
            constraint_evaluations=(),
            certified=(len(violations) == 0),
        )