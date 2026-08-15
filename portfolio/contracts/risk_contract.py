# portfolio/contracts/risk_contract.py
import dataclasses
from datetime import datetime
from research.governance.serialization import CanonicalSerializer

@dataclasses.dataclass(frozen=True)
class RiskSnapshot:
    """
    The immutable state of risk estimates at time T.
    """
    snapshot_id: str
    timestamp: datetime
    asset_universe_hash: str  # Must match the UniverseCertificate's hash
    covariance_hash: str      # Pointer to the materialized covariance matrix
    factor_model_hash: str    # Pointer to the active factor exposures
    
    @property
    def snapshot_hash(self) -> str:
        return CanonicalSerializer.hash(self)
