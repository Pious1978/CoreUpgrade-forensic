@dataclass(frozen=True)
class AuditResult:
    """Immutable, tamper-evident audit execution artifact with multi-format export capabilities."""
    audit_name: str
    audit_id: str
    category: str
    status: AuditStatus
    score: Optional[float]
    weight: float
    findings: tuple  # Tuple for deep immutability
    duration_seconds: float
    run_id: str
    executed_at: datetime
    started_at: datetime
    completed_at: datetime
    config_fingerprint: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    execution_id: str = field(default_factory=lambda: str(uuid4()))
    result_id: str = field(default_factory=lambda: str(uuid4()))
    attempt_number: int = 1
    max_retries: int = 0
    attempts: tuple = field(default_factory=tuple)
    version: str = "1.0"
    description: str = ""
    tags: tuple = field(default_factory=tuple)
    execution_state: AuditExecutionState = AuditExecutionState.INITIALIZED
    error_message: Optional[str] = None
    cleanup_failed: bool = False
    cleanup_error: Optional[str] = None
    records_checked: int = 0
    checks_executed: int = 0
    warnings_generated: int = 0
    parent_execution_id: Optional[str] = None
    dependency_status: MappingProxyType = field(default_factory=lambda: MappingProxyType({}))

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the result into a standard Python dictionary."""
        return {
            "result_id": self.result_id,
            "run_id": self.run_id,
            "execution_id": self.execution_id,
            "parent_execution_id": self.parent_execution_id,
            "audit_id": self.audit_id,
            "audit_name": self.audit_name,
            "category": self.category,
            "status": self.status.value,
            "score": self.score,
            "weight": self.weight,
            "duration_seconds": self.duration_seconds,
            "executed_at": self.executed_at.isoformat(),
            "execution_state": self.execution_state.value,
            "records_checked": self.records_checked,
            "checks_executed": self.checks_executed,
            "warnings_generated": self.warnings_generated,
            "findings_count": len(self.findings),
            "findings": [f.__dict__ for f in self.findings],
            "attempts": [a.__dict__ for a in self.attempts],
            "error_message": self.error_message
        }

    def to_json(self) -> str:
        """Serializes the result to a JSON string."""
        return json.dumps(self.to_dict(), default=str, sort_keys=True)

    def to_dataframe(self):
        """Exports audit findings into a Pandas DataFrame for analytics."""
        import pandas as pd
        rows = []
        for f in self.findings:
            rows.append({
                "result_id": self.result_id,
                "audit_id": self.audit_id,
                "finding_id": f.finding_id,
                "fingerprint": f.fingerprint,
                "severity": f.severity.value if hasattr(f.severity, "value") else str(f.severity),
                "title": f.title,
                "description": f.description,
                "timestamp": f.timestamp
            })
        return pd.DataFrame(rows)
