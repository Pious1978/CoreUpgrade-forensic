# portfolio/risk/contracts/covariance_contract.py
import dataclasses
from research.governance.serialization import CanonicalSerializer

@dataclasses.dataclass(frozen=True)
class CovarianceMatrixArtifact:
    matrix_id: str
    universe_hash: str
    lookback_days: int
    methodology: str       # e.g., "LEDOIT_WOLF"
    shrinkage_method: str  # e.g., "CONSTANT_CORRELATION"
    data_snapshot_hash: str
    
    # In practice, this hashes a serialized, flattened tuple of the Decimal matrix
    matrix_hash: str 
    
    @property
    def artifact_hash(self) -> str:
        return CanonicalSerializer.hash(self)

# portfolio/risk/contracts/factor_contract.py
@dataclasses.dataclass(frozen=True)
class FactorExposureArtifact:
    model_id: str
    version: str
    universe_hash: str
    methodology_hash: str
    data_snapshot_hash: str
    exposures_hash: str
    
    @property
    def artifact_hash(self) -> str:
        return CanonicalSerializer.hash(self)
