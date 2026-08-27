"""
Certification Result

Represents the immutable output envelope of the CertificationEngine evaluation,
encapsulating institutional verdicts, policy versions, audit metrics, and timestamps.
"""

from dataclasses import dataclass, field
from typing import Tuple, Dict, Any, Optional


@dataclass(frozen=True)
class CertificationResult:
    certification_id: str
    issued_at: str
    policy_version: str
    master_verdict: str  # "CERTIFIED" or "REJECTED"
    registered_gate_count: int
    executed_gate_count: int
    failure_reason: Optional[str]
    execution_results: Tuple[Any, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serializes the certification result into a standardized, deterministic dictionary payload.
        """
        return {
            "payload": {
                "certification_id": self.certification_id,
                "issued_at": self.issued_at,
                "policy_version": self.policy_version,
                "master_verdict": self.master_verdict,
                "registered_gate_count": self.registered_gate_count,
                "executed_gate_count": self.executed_gate_count,
                "failure_reason": self.failure_reason,
                "execution_results": list(self.execution_results)
            }
        }
