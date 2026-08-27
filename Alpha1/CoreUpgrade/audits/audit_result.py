import datetime
import json
import platform
import socket
from enum import Enum


class AuditCategory(str, Enum):
    DATABASE = "DATABASE"
    SCHEMA = "SCHEMA"
    MARKET_DATA = "MARKET_DATA"
    RISK = "RISK"
    TARGET = "TARGET"
    PIPELINE = "PIPELINE"
    RESEARCH = "RESEARCH"
    LIQUIDITY = "LIQUIDITY"


class AuditSeverity(str, Enum):
    PASS = "PASS"
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    SKIPPED = "SKIPPED"


class AuditResult:
    """
    Standardizes and validates the structured output payload for all framework audits.
    Enforces strict contract enforcement and schema compliance before serialization.
    """

    def __init__(
        self,
        audit_name: str,
        category: AuditCategory,
        severity: AuditSeverity,
        execution_status: ExecutionStatus,
        run_id: str,
        audit_version: str,
        duration_ms: float = 0.0,
        metrics: dict = None,
        findings: list = None,
        score: dict = None,
        error: dict = None,
        timestamp: str = None,
        schema_version: str = "1.0"
    ):
        self.audit_name = audit_name
        
        # Enforce enum values (handles string inputs or direct Enum types gracefully)
        self.category = (
            category.value if isinstance(category, AuditCategory) else category
        )
        self.severity = (
            severity.value if isinstance(severity, AuditSeverity) else severity
        )
        self.execution_status = (
            execution_status.value if isinstance(execution_status, ExecutionStatus) else execution_status
        )
        
        self.run_id = run_id
        
        # Timezone-aware UTC timestamp generation for explicit traceability
        self.timestamp = (
            timestamp 
            or datetime.datetime.now(datetime.timezone.utc).isoformat()
        )
        
        self.duration_ms = duration_ms
        self.audit_version = audit_version
        self.schema_version = schema_version
        
        self.metrics = metrics or {}
        self.findings = findings or []
        self.score = score
        self.error = error

    def validate(self) -> list:
        """
        Validates contract requirements and returns a list of error strings.
        Ensures malformed payloads fail early before hitting persistence or reporting layers.
        """
        errors = []

        if not self.audit_name:
            errors.append("Missing audit_name")

        if not self.run_id:
            errors.append("Missing run_id")

        if self.category not in [c.value for c in AuditCategory]:
            errors.append(f"Invalid category: {self.category}")

        if self.severity not in [s.value for s in AuditSeverity]:
            errors.append(f"Invalid severity: {self.severity}")

        if self.execution_status not in [e.value for e in ExecutionStatus]:
            errors.append(f"Invalid execution_status: {self.execution_status}")

        return errors

    def to_dict(self) -> dict:
        """
        Serializes the audit result into the institutional schema contract.
        Triggers validation to guarantee absolute compliance before export.
        """
        validation_errors = self.validate()
        if validation_errors:
            raise ValueError(f"AuditResult schema validation failed: {validation_errors}")

        payload = {
            "schema_version": self.schema_version,
            "audit_name": self.audit_name,
            "execution": {
                "run_id": self.run_id,
                "timestamp": self.timestamp,
                "duration_ms": self.duration_ms,
                "audit_version": self.audit_version
            },
            "classification": {
                "category": self.category,
                "severity": self.severity,
                "execution_status": self.execution_status
            },
            "metrics": self.metrics,
            "findings": self.findings,
            "environment": {
                "hostname": socket.gethostname(),
                "python": platform.python_version()
            }
        }

        if self.score:
            payload["score"] = self.score

        if self.error:
            payload["error"] = self.error

        return payload

    def to_json(self) -> str:
        """Serializes the institutional contract directly into a pretty-printed JSON string."""
        return json.dumps(
            self.to_dict(),
            indent=4,
            default=str
        )
