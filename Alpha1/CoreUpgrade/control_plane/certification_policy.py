"""
Certification Policy

Defines the institutional rules, thresholds, and blocking criteria
used by the CertificationEngine to evaluate audit run results.
"""

from dataclasses import dataclass, field
from typing import Set


@dataclass(frozen=True)
class CertificationPolicy:
    policy_version: str = "v1.0"
    minimum_gate_count: int = 1
    block_on_execution_mismatch: bool = True
    blocking_statuses: Set[str] = field(
        default_factory=lambda: {"FAIL", "CRITICAL", "SECURITY_FAILURE"}
    )
