# portfolio/certification/theorems/theorem_exposure_001.py
from decimal import Decimal
from typing import Tuple
from portfolio.contracts.portfolio_certificate import TargetWeight, PortfolioExposure

class ExposureConservationTheorem:
    id = "THEOREM-EXPOSURE-001"
    version = "1.0.0"
    
    @classmethod
    def verify(cls, weights: Tuple[TargetWeight, ...], exposure: PortfolioExposure) -> dict:
        """
        Invariant 1: Sum of target weights + cash weight must equal 1.0 (Decimal).
        Invariant 2: No duplicate instrument IDs allowed in target weights.
        """
        # Check for duplicate instrument IDs (prevents double-allocation ambiguity)
        instrument_ids = [tw.instrument_id for tw in weights]
        if len(instrument_ids) != len(set(instrument_ids)):
            return {
                "certified": False,
                "reason": "Exposure violation: Duplicate instrument IDs detected in target weights."
            }
            
        # Sum weights
        sum_weights = sum((tw.weight for tw in weights), Decimal("0.0"))
        total_portfolio_allocation = sum_weights + exposure.cash_weight
        
        is_conserved = (total_portfolio_allocation == Decimal("1.0")) and (exposure.invested_weight == sum_weights)
        
        return {
            "certified": is_conserved,
            "observed_exposure": total_portfolio_allocation,
            "invested_weight": sum_weights,
            "cash_weight": exposure.cash_weight,
            "reason": None if is_conserved else f"Exposure mismatch: Σ weights ({sum_weights}) + cash ({exposure.cash_weight}) != 1.0"
        }
