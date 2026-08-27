# portfolio/optimization/engines/objective_engine.py
import dataclasses
from typing import Tuple, Dict, Any
from portfolio.contracts.alpha_contract import CertifiedAlphaVector
from portfolio.contracts.risk_contract import RiskSnapshot
from research.governance.serialization import CanonicalSerializer

@dataclasses.dataclass(frozen=True)
class ObjectiveFunction:
    """
    Represents the abstract mathematical objective function.
    Bound to the complete RiskSnapshot hash to preserve full risk lineage.
    """
    objective_id: str
    objective_type: str  # e.g., "MEAN_VARIANCE"
    parameters: Tuple[Tuple[str, Any], ...]  # e.g., (("risk_aversion", "2.5"),)
    alpha_vector_hash: str
    risk_snapshot_hash: str  # Fully binds to the immutable RiskSnapshot artifact
    
    @property
    def objective_hash(self) -> str:
        return CanonicalSerializer.hash(self)

class ObjectiveEngine:
    """
    Compiles certified research outputs and objective parameters into 
    an abstract mathematical representation.
    """
    @staticmethod
    def build(
        objective_id: str,
        objective_type: str,
        alpha_vector: CertifiedAlphaVector,
        risk_snapshot: RiskSnapshot,
        parameters: Dict[str, Any]
    ) -> ObjectiveFunction:
        
        # Sort parameters alphabetically to guarantee deterministic hashing
        sorted_params = tuple(sorted((str(k), str(v)) for k, v in parameters.items()))
        
        return ObjectiveFunction(
            objective_id=objective_id,
            objective_type=objective_type,
            parameters=sorted_params,
            alpha_vector_hash=alpha_vector.vector_hash,
            risk_snapshot_hash=risk_snapshot.snapshot_hash
        )
