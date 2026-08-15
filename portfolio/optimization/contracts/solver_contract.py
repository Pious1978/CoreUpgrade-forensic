# portfolio/optimization/contracts/solver_contract.py
import dataclasses
from research.governance.serialization import CanonicalSerializer

@dataclasses.dataclass(frozen=True)
class SolverMetadata:
    """
    Captures the exact numerical and execution environment of the solver backend.
    Required by THEOREM-OPTIMIZER-REPLAY-001 to prevent floating-point drift.
    """
    solver_name: str          # e.g., "ECOS", "OSQP", "SCIPY"
    solver_version: str       # e.g., "3.0.0"
    backend: str              # e.g., "CVXPY"
    numerical_precision: str  # e.g., "float64"
    environment_hash: str     # Hash of python, numpy, scipy, cvxpy, and BLAS versions
    
    @property
    def metadata_hash(self) -> str:
        return CanonicalSerializer.hash(self)
