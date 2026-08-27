# portfolio/contracts/portfolio_certificate.py
import dataclasses
from datetime import datetime
from decimal import Decimal
from typing import Tuple
from portfolio.contracts.asset_contract import AssetIdentity
from research.governance.serialization import CanonicalSerializer

@dataclasses.dataclass(frozen=True)
class OptimizerIdentity:
    optimizer_id: str
    version: str
    implementation_hash: str

@dataclasses.dataclass(frozen=True)
class ConstraintEvaluation:
    constraint_id: str
    status: str  # "PASS", "FAIL", "SOFT_VIOLATION"
    observed_value: Decimal
    limit: Decimal

@dataclasses.dataclass(frozen=True)
class TargetWeight:
    instrument_id: str
    weight: Decimal

@dataclasses.dataclass(frozen=True)
class PortfolioExposure:
    invested_weight: Decimal
    cash_weight: Decimal
    
    def __post_init__(self):
        if self.invested_weight + self.cash_weight != Decimal("1.0"):
            raise ValueError("Exposure invariant violated: Σ weights + cash must equal 1.0")

@dataclasses.dataclass(frozen=True)
class PortfolioCertificate:
    """The Immutable Handshake to the Execution Engine."""
    portfolio_id: str
    timestamp: datetime
    
    # Cryptographic Lineage
    alpha_vector_hash: str
    universe_hash: str
    risk_hash: str
    optimizer_identity: OptimizerIdentity
    
    # State & Compliance
    exposure: PortfolioExposure
    target_weights: Tuple[TargetWeight, ...]
    constraint_evaluations: Tuple[ConstraintEvaluation, ...]
    
    certified: bool  # True iff ALL Layer 2 Portfolio Theorems passed.
    
    @property
    def certificate_hash(self) -> str:
        return CanonicalSerializer.hash(self)
