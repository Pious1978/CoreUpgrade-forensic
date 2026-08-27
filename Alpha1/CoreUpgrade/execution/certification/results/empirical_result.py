"""
Immutable Empirical Result Contract & Execution Results

Authority:
    Execution Layer Certification Results
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Mapping
from types import MappingProxyType

def freeze(obj: Any) -> Any:
    """
    Recursively freezes mutable data structures (dicts -> MappingProxyType, lists/sets -> tuples)
    to guarantee deep immutability across the audit record.
    """
    if isinstance(obj, MappingProxyType):
        return obj
    if isinstance(obj, dict):
        return MappingProxyType({str(k): freeze(v) for k, v in obj.items()})
    if isinstance(obj, (list, set, tuple)):
        return tuple(freeze(x) for x in obj)
    return obj

@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """
    Strongly-typed result container for individual theorem evaluations,
    incorporating deep immutability and failure taxonomy.
    """
    certified: bool
    failure_origin: Optional[str] = None  # ENGINE, THEOREM, DEPENDENCY, ENVIRONMENT, DATA, SERIALIZATION, CONFIGURATION
    failure_type: Optional[str] = None
    severity: str = "ERROR"
    reason_code: str = "UNKNOWN"
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    evidence: Mapping[str, Any] = field(default_factory=dict)
    proof: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, 'diagnostics', freeze(dict(self.diagnostics)))
        object.__setattr__(self, 'evidence', freeze(dict(self.evidence)))
        object.__setattr__(self, 'proof', freeze(dict(self.proof)))

@dataclass(frozen=True, slots=True)
class ExecutionEmpiricalResult:
    """
    Immutable, strongly-typed master result object capturing the full execution audit record,
    separating deterministic proof data from runtime diagnostics with frozen mappings.
    """
    schema_version: str
    proof_schema: str
    certified: bool
    theorem_id: str
    theorem_version: str
    engine_version: str
    execution_timestamp: str
    total_theorems: int
    passed: int
    failed: int
    execution_order: List[str]
    registry_fingerprint: str
    provenance: Any
    results: Any
    diagnostics: Any
    master_proof_hash: str
    duration_ms: float
    reason: str | None

    def __post_init__(self):
        object.__setattr__(self, 'provenance', freeze(self.provenance))
        object.__setattr__(self, 'results', freeze(self.results))
        object.__setattr__(self, 'diagnostics', freeze(self.diagnostics))
        object.__setattr__(self, 'execution_order', tuple(self.execution_order))

    def to_dict(self) -> dict:
        """Exports the strongly-typed result object into a canonical dictionary format recursively."""
        def unfreeze(val: Any) -> Any:
            if isinstance(val, MappingProxyType):
                return {k: unfreeze(v) for k, v in val.items()}
            if isinstance(val, tuple):
                return [unfreeze(x) for x in val]
            return val

        return {
            "schema_version": self.schema_version,
            "proof_schema": self.proof_schema,
            "certified": self.certified,
            "theorem_id": self.theorem_id,
            "theorem_version": self.theorem_version,
            "engine_version": self.engine_version,
            "execution_timestamp": self.execution_timestamp,
            "total_theorems": self.total_theorems,
            "passed": self.passed,
            "failed": self.failed,
            "execution_order": list(self.execution_order),
            "registry_fingerprint": self.registry_fingerprint,
            "provenance": unfreeze(self.provenance),
            "results": unfreeze(self.results),
            "diagnostics": unfreeze(self.diagnostics),
            "master_proof_hash": self.master_proof_hash,
            "duration_ms": self.duration_ms,
            "reason": self.reason,
        }