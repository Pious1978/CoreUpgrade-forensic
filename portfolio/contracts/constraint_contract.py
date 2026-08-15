# portfolio/contracts/constraint_contract.py
import dataclasses
from decimal import Decimal
from typing import Tuple, Any
from research.governance.serialization import CanonicalSerializer

@dataclasses.dataclass(frozen=True)
class PortfolioConstraint:
    """
    A hard or soft limit imposed on the allocation engine.
    Examples: MAX_POSITION_SIZE, MAX_SECTOR_EXPOSURE, MAX_TURNOVER.
    """
    constraint_id: str
    constraint_type: str
    limit: Decimal
    severity: str  # e.g., "HARD", "SOFT"
    parameters: Tuple[Tuple[str, Any], ...]  # e.g., (("sector", "TECHNOLOGY"),)
    
    @property
    def constraint_hash(self) -> str:
        return CanonicalSerializer.hash(self)

@dataclasses.dataclass(frozen=True)
class ConstraintSet:
    """The complete set of rules governing a specific portfolio optimization."""
    ruleset_id: str
    constraints: Tuple[PortfolioConstraint, ...]
    
    @property
    def ruleset_hash(self) -> str:
        return CanonicalSerializer.hash(self)
