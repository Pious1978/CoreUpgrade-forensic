from dataclasses import dataclass, field
from typing import Mapping, Tuple, Any
from core.immutable import freeze_mapping, freeze_findings


@dataclass(frozen=True)
class AuditArtifact:
    """
    Normalized immutable execution artifact returned by the AuditExecutor
    with enforced deep immutability mapping proxies.
    """
    audit_id: str
    name: str
    status: str  # SUCCESS, FAILED, WARNING
    score: float
    duration_seconds: float
    findings: Tuple[Mapping[str, Any], ...] = ()
    metrics: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, 'findings', freeze_findings(self.findings))
        object.__setattr__(self, 'metrics', freeze_mapping(self.metrics))
        object.__setattr__(self, 'metadata', freeze_mapping(self.metadata))
