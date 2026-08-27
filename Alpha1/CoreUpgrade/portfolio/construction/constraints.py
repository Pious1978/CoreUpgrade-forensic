# portfolio/construction/constraints.py
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Tuple

from portfolio.contracts.constraint_contract import PortfolioConstraint
from portfolio.contracts.portfolio_certificate import TargetWeight, ConstraintEvaluation
from portfolio.universe.metadata_provider import PointInTimeMetadata

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
        portfolio_aum: Decimal
    ) -> ConstraintEvaluation:
        pass

class MaxPositionSizeEvaluator(AbstractConstraintEvaluator):
    """
    Concentration Risk Constraint: 
    Ensures no single asset exceeds a predefined percentage of the total portfolio AUM.
    """
    def evaluate(
        self, 
        constraint: PortfolioConstraint, 
        weights: Tuple[TargetWeight, ...],
        metadata: PointInTimeMetadata,
        portfolio_aum: Decimal
    ) -> ConstraintEvaluation:
        
        limit = constraint.limit
        max_observed = Decimal("0.0")
        violator = None
        
        for tw in weights:
            if tw.weight > max_observed:
                max_observed = tw.weight
                violator = tw.instrument_id
                
        status = "PASS" if max_observed <= limit else "FAIL"
        if status == "FAIL" and constraint.severity == "SOFT":
            status = "SOFT_VIOLATION"
            
        return ConstraintEvaluation(
            constraint_id=constraint.constraint_id,
            status=status,
            observed_value=max_observed,
            limit=limit
        )

class MaxSectorExposureEvaluator(AbstractConstraintEvaluator):
    """
    Sector Concentration Constraint:
    Ensures the total weight allocated to a specific sector does not exceed the limit.
    """
    def evaluate(
        self, 
        constraint: PortfolioConstraint, 
        weights: Tuple[TargetWeight, ...],
        metadata: PointInTimeMetadata,
        portfolio_aum: Decimal
    ) -> ConstraintEvaluation:
        
        limit = constraint.limit
        
        # Extract the target sector from the constraint parameters (e.g., (("sector", "TECHNOLOGY"),))
        constraint_params = dict(constraint.parameters)
        target_sector = constraint_params.get("sector")
        
        if not target_sector:
            raise ValueError(f"MaxSectorExposureEvaluator requires a 'sector' parameter. Found: {constraint_params}")
        
        observed_exposure = Decimal("0.0")
        for tw in weights:
            # Requires PointInTimeMetadata to supply exact historical sector classifications
            if metadata.get_sector(tw.instrument_id) == target_sector:
                observed_exposure += tw.weight
                
        status = "PASS" if observed_exposure <= limit else "FAIL"
        if status == "FAIL" and constraint.severity == "SOFT":
            status = "SOFT_VIOLATION"
        
        return ConstraintEvaluation(
            constraint_id=constraint.constraint_id,
            status=status,
            observed_value=observed_exposure,
            limit=limit
        )

class MaxParticipationRateEvaluator(AbstractConstraintEvaluator):
    """
    Execution Feasibility Constraint:
    Ensures the target position does not demand an unexecutable percentage of the asset's Average Daily Volume (ADV).
    Sits perfectly at the intersection of Allocation (Weight), Reality (Metadata/ADV), and Execution (Shares).
    """
    def evaluate(
        self, 
        constraint: PortfolioConstraint, 
        weights: Tuple[TargetWeight, ...],
        metadata: PointInTimeMetadata,
        portfolio_aum: Decimal
    ) -> ConstraintEvaluation:
        
        limit_pct = constraint.limit  # e.g., Decimal("0.10") for 10% of ADV
        
        max_observed_participation = Decimal("0.0")
        violator_id = None
        
        for tw in weights:
            # Get T-0 Reality Data
            adv_shares = metadata.get_adv_30d(tw.instrument_id)
            current_price = metadata.get_price(tw.instrument_id)
            
            if adv_shares <= Decimal("0") or current_price <= Decimal("0"):
                continue # Skip or handle illiquid/halted asset error depending on policy
            
            # Translate Weight to Absolute Shares
            proposed_capital = tw.weight * portfolio_aum
            proposed_shares = proposed_capital / current_price
            
            # Calculate required participation rate
            participation_rate = proposed_shares / adv_shares
            
            if participation_rate > max_observed_participation:
                max_observed_participation = participation_rate
                violator_id = tw.instrument_id
                
            if participation_rate > limit_pct:
                return ConstraintEvaluation(
                    constraint_id=constraint.constraint_id,
                    status="FAIL",
                    observed_value=max_observed_participation,
                    limit=limit_pct
                )
                
        return ConstraintEvaluation(
            constraint_id=constraint.constraint_id,
            status="PASS",
            observed_value=max_observed_participation,
            limit=limit_pct
        )
