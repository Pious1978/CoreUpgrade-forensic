# portfolio/construction/constraints.py

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, List, Tuple

from portfolio.contracts.constraint_contract import PortfolioConstraint
from portfolio.contracts.portfolio_certificate import (
    TargetWeight,
    ConstraintEvaluation,
)
from portfolio.universe.metadata_provider import PointInTimeMetadata
from research.adapter import ResearchCandidate


class AbstractConstraintEvaluator(ABC):
    """
    Base class for independent, deterministic constraint verification.

    Evaluates proposed weights against Point-in-Time reality before execution.
    """

    @abstractmethod
    def evaluate(
        self,
        constraint: PortfolioConstraint,
        weights: Tuple[TargetWeight, ...],
        metadata: PointInTimeMetadata,
        portfolio_aum: Decimal,
    ) -> ConstraintEvaluation:
        pass


class MaxPositionSizeEvaluator(AbstractConstraintEvaluator):
    """
    Concentration Risk Constraint.

    Ensures no single asset exceeds a predefined percentage
    of the total portfolio AUM.
    """

    def evaluate(
        self,
        constraint: PortfolioConstraint,
        weights: Tuple[TargetWeight, ...],
        metadata: PointInTimeMetadata,
        portfolio_aum: Decimal,
    ) -> ConstraintEvaluation:

        limit = constraint.limit
        max_observed = Decimal("0.0")

        for tw in weights:
            if tw.weight > max_observed:
                max_observed = tw.weight

        status = "PASS" if max_observed <= limit else "FAIL"

        if status == "FAIL" and constraint.severity == "SOFT":
            status = "SOFT_VIOLATION"

        return ConstraintEvaluation(
            constraint_id=constraint.constraint_id,
            status=status,
            observed_value=max_observed,
            limit=limit,
        )


class MaxSectorExposureEvaluator(AbstractConstraintEvaluator):
    """
    Sector Concentration Constraint.

    Ensures the total weight allocated to a specific sector
    does not exceed the configured limit.
    """

    def evaluate(
        self,
        constraint: PortfolioConstraint,
        weights: Tuple[TargetWeight, ...],
        metadata: PointInTimeMetadata,
        portfolio_aum: Decimal,
    ) -> ConstraintEvaluation:

        limit = constraint.limit

        # Example:
        # parameters=(("sector", "TECHNOLOGY"),)
        constraint_params = dict(constraint.parameters)
        target_sector = constraint_params.get("sector")

        if not target_sector:
            raise ValueError(
                "MaxSectorExposureEvaluator requires a 'sector' "
                f"parameter. Found: {constraint_params}"
            )

        observed_exposure = Decimal("0.0")

        for tw in weights:
            # Point-in-Time metadata must provide the historical
            # sector classification applicable to the evaluation date.
            if metadata.get_sector(tw.instrument_id) == target_sector:
                observed_exposure += tw.weight

        status = "PASS" if observed_exposure <= limit else "FAIL"

        if status == "FAIL" and constraint.severity == "SOFT":
            status = "SOFT_VIOLATION"

        return ConstraintEvaluation(
            constraint_id=constraint.constraint_id,
            status=status,
            observed_value=observed_exposure,
            limit=limit,
        )


class MaxParticipationRateEvaluator(AbstractConstraintEvaluator):
    """
    Execution Feasibility Constraint.

    Ensures the target position does not demand an unexecutable
    percentage of the asset's Average Daily Volume (ADV).

    This sits at the intersection of:

        Allocation Weight
            ->
        Point-in-Time Reality
            ->
        Shares Required
            ->
        Execution Feasibility
    """

    def evaluate(
        self,
        constraint: PortfolioConstraint,
        weights: Tuple[TargetWeight, ...],
        metadata: PointInTimeMetadata,
        portfolio_aum: Decimal,
    ) -> ConstraintEvaluation:

        limit_pct = constraint.limit

        max_observed_participation = Decimal("0.0")

        for tw in weights:

            # T-0 / Point-in-Time reality.
            adv_shares = metadata.get_adv_30d(tw.instrument_id)
            current_price = metadata.get_price(tw.instrument_id)

            # Invalid market data cannot produce a meaningful
            # participation calculation.
            #
            # The current policy is to skip it here. A stricter
            # production policy may instead convert this to FAIL.
            if (
                adv_shares <= Decimal("0")
                or current_price <= Decimal("0")
            ):
                continue

            # Convert portfolio weight into absolute capital.
            proposed_capital = tw.weight * portfolio_aum

            # Convert capital into shares.
            proposed_shares = proposed_capital / current_price

            # Required percentage of ADV.
            participation_rate = proposed_shares / adv_shares

            if participation_rate > max_observed_participation:
                max_observed_participation = participation_rate

            if participation_rate > limit_pct:

                status = "FAIL"

                if constraint.severity == "SOFT":
                    status = "SOFT_VIOLATION"

                return ConstraintEvaluation(
                    constraint_id=constraint.constraint_id,
                    status=status,
                    observed_value=max_observed_participation,
                    limit=limit_pct,
                )

        return ConstraintEvaluation(
            constraint_id=constraint.constraint_id,
            status="PASS",
            observed_value=max_observed_participation,
            limit=limit_pct,
        )


class PortfolioConstraintEngine:
    """
    Portfolio-level constraint/risk interface used by the allocator.

    This class is deliberately kept separate from the individual
    evaluators above.

    The evaluators answer:

        "Does this proposed portfolio violate constraint X?"

    This engine provides the higher-level interfaces required by
    portfolio construction:

        - risk-adjusted candidate scoring
        - mandatory cash reserve
        - maximum position concentration

    The actual immutable PortfolioConstraint / ConstraintSet contracts
    remain the authoritative governance objects for formal certification.
    """

    DEFAULT_MIN_CASH_RESERVE = Decimal("0.10")
    DEFAULT_MAX_CONCENTRATION = Decimal("0.45")

    def __init__(
        self,
        min_cash_reserve: Decimal = DEFAULT_MIN_CASH_RESERVE,
        max_concentration: Decimal = DEFAULT_MAX_CONCENTRATION,
    ) -> None:

        min_cash_reserve = Decimal(str(min_cash_reserve))
        max_concentration = Decimal(str(max_concentration))

        if not (
            Decimal("0") <= min_cash_reserve < Decimal("1")
        ):
            raise ValueError(
                "min_cash_reserve must be between 0 and 1."
            )

        if not (
            Decimal("0") < max_concentration <= Decimal("1")
        ):
            raise ValueError(
                "max_concentration must be between 0 and 1."
            )

        self.min_cash_reserve = float(min_cash_reserve)
        self.max_concentration = float(max_concentration)

        self._evaluators = {
            "MAX_POSITION_SIZE": MaxPositionSizeEvaluator(),
            "MAX_SECTOR_EXPOSURE": MaxSectorExposureEvaluator(),
            "MAX_PARTICIPATION_RATE": MaxParticipationRateEvaluator(),
        }

    def apply_risk_adjustments(
        self,
        approved_candidates: List[ResearchCandidate],
    ) -> Dict[str, float]:
        """
        Convert approved research candidates into deterministic
        allocation scores.

        The score is adjusted downward according to volatility.

        Formula:

            adjusted_score =
                candidate.score * (1 - volatility_penalty)

        Where volatility_penalty is bounded to [0, 1].

        This keeps the allocator independent of scanner-specific
        implementations while ensuring higher-volatility candidates
        receive less allocation weight.
        """

        adjusted_scores: Dict[str, float] = {}

        for candidate in approved_candidates:

            base_score = max(
                0.0,
                float(candidate.score),
            )

            volatility = min(
                1.0,
                max(
                    0.0,
                    float(candidate.volatility_score),
                ),
            )

            adjusted_score = base_score * (1.0 - volatility)

            if adjusted_score > 0:
                adjusted_scores[candidate.symbol] = adjusted_score

        return adjusted_scores

    def get_evaluator(
        self,
        constraint_type: str,
    ) -> AbstractConstraintEvaluator:
        """
        Return the deterministic evaluator registered for a
        PortfolioConstraint type.
        """

        try:
            return self._evaluators[constraint_type]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported constraint type: {constraint_type}"
            ) from exc

    def evaluate(
        self,
        constraint: PortfolioConstraint,
        weights: Tuple[TargetWeight, ...],
        metadata: PointInTimeMetadata,
        portfolio_aum: Decimal,
    ) -> ConstraintEvaluation:
        """
        Dispatch a PortfolioConstraint to its registered evaluator.
        """

        evaluator = self.get_evaluator(constraint.constraint_type)

        return evaluator.evaluate(
            constraint=constraint,
            weights=weights,
            metadata=metadata,
            portfolio_aum=portfolio_aum,
        )


__all__ = [
    "AbstractConstraintEvaluator",
    "MaxPositionSizeEvaluator",
    "MaxSectorExposureEvaluator",
    "MaxParticipationRateEvaluator",
    "PortfolioConstraintEngine",
]

