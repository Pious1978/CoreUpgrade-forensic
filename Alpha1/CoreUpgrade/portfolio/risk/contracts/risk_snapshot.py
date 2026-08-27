# portfolio/risk/contracts/risk_snapshot.py
import dataclasses
from datetime import datetime
from research.governance.serialization import CanonicalSerializer

@dataclasses.dataclass(frozen=True)
class NumericalEnvironment:
    """Guarantees linear algebra reproducibility."""
    python_version: str
    numpy_version: str
    blas_vendor: str
    linear_algebra_backend: str

@dataclasses.dataclass(frozen=True)
class RiskSnapshot:
    snapshot_id: str
    timestamp: datetime
    universe_hash: str
    covariance_hash: str
    factor_hash: str
    price_data_snapshot_hash: str
    numerical_environment: NumericalEnvironment
    model_version: str
    
    @property
    def snapshot_hash(self) -> str:
        return CanonicalSerializer.hash(self)
