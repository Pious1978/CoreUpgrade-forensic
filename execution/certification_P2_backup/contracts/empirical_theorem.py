"""
Empirical Theorem Base Contract

Authority:
    Execution Layer Certification
"""
from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any
from packaging.version import Version
from execution.manifest import EXECUTION_ENGINE_VERSION
from execution.certification.results.empirical_result import ExecutionResult

class EmpiricalTheorem(ABC):
    """
    Standardized abstract base class enforcing a strict interface contract 
    for all decentralized empirical execution theorems, including institutional lineage metadata,
    dependency mapping, failure severity, and semantic version compatibility.
    """
    id: str
    version: str
    required_engine_version: str = EXECUTION_ENGINE_VERSION
    depends_on: Tuple[str, ...] = ()
    severity: str = "ERROR"  # INFO, WARNING, ERROR, FATAL

    # Institutional audit lineage metadata
    authority: str = "Execution Governance"
    domain: str = "Order Lifecycle & Event Sourcing"
    created_at: str = "2026-08-01"
    deprecated: bool = False

    ALLOWED_PROOF_FIELDS = {
        "certified",
        "failure_type",
        "failure_origin",
        "severity",
        "rule",
        "reason_code",
        "evidence",
        "proofs",
    }

    @classmethod
    def supports(cls, engine_version: str) -> bool:
        """
        Verifies semantic version compatibility using packaging.version.Version.
        Requires same major version and running version >= required version.
        """
        try:
            required = Version(cls.required_engine_version)
            running = Version(engine_version)
            return (
                required.major == running.major
                and running >= required
            )
        except Exception:
            return False

    @classmethod
    @abstractmethod
    def verify(cls, *args, **kwargs) -> dict | ExecutionResult:
        """Core theorem execution logic returning evidence and claims."""
        pass