from dataclasses import dataclass, field
from typing import Mapping, Tuple, Any, Optional
import json
import hashlib

from core.execution_manifest import ExecutionManifest
from core.immutable import freeze_findings, freeze_mapping
from core.serializer import make_serializable


@dataclass(frozen=True)
class AuditRunResult:
    """
    Institutional business audit run result featuring post-initialization
    deep recursive freezing across all findings, scores, and artifacts.
    """
    run_id: str
    timestamp: str
    status: str  # SUCCESS, PARTIAL, FAILED
    duration_seconds: float
    audits_executed: int
    manifest: ExecutionManifest
    run_fingerprint: str
    report_path: Optional[str] = None

    findings: Tuple[Mapping[str, Any], ...] = ()
    scores: Mapping[str, float] = field(default_factory=dict)
    artifacts: Mapping[str, Any] = field(default_factory=dict)
    failed_audits: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "findings", freeze_findings(self.findings))
        object.__setattr__(self, "scores", freeze_mapping(self.scores))
        object.__setattr__(self, "artifacts", freeze_mapping(self.artifacts))
        object.__setattr__(self, "failed_audits", freeze_mapping(self.failed_audits))

    def summary(self) -> Mapping[str, Any]:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "status": self.status,
            "duration_seconds": self.duration_seconds,
            "audits_executed": self.audits_executed,
            "failed_count": len(self.failed_audits),
            "total_findings": len(self.findings),
            "run_fingerprint": self.run_fingerprint,
            "git_commit": self.manifest.git_commit,
            "framework_version": self.manifest.framework_version,
            "environment": self.manifest.environment,
            "report_path": self.report_path
        }

    def export(self, format: str = "json") -> str:
        if format.lower() == "json":
            raw_data = {
                "summary": dict(self.summary()),
                "manifest": make_serializable(self.manifest),
                "scores": dict(self.scores),
                "findings": [make_serializable(f) for f in self.findings],
                "failed_audits": dict(self.failed_audits),
                "artifacts": make_serializable(self.artifacts)
            }
            return json.dumps(raw_data, indent=2, default=str)
        raise ValueError(f"Unsupported export format: {format}")


def compute_run_fingerprint(
    registry_fingerprint: str,
    git_commit: str,
    config_hash: str,
    parameter_hash: str
) -> str:
    """Computes a canonical cryptographic fingerprint for absolute reproducibility."""
    payload = {
        "registry": registry_fingerprint,
        "git": git_commit,
        "config": config_hash,
        "parameters": parameter_hash
    }
    canonical = json.dumps(payload, sort_keys=True)
    hasher = hashlib.sha256()
    hasher.update(canonical.encode("utf-8"))
    return f"RUN-FP-{hasher.hexdigest()[:16].upper()}"
