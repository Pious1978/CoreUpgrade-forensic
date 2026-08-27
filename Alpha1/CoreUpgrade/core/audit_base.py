class BaseAudit(ABC):
    """Clean business logic contract stripped of orchestration concerns."""

    def __init__(self, config: AuditConfig, context: AuditContext):
        self.config = config
        self.context = context
        self.findings: List[Finding] = []
        self._finding_fingerprints: Set[str] = set()
        self.records_checked: int = 0
        self.checks_executed: int = 0
        self.warnings_generated: int = 0

    @property
    @abstractmethod
    def audit_id(self) -> str:
        pass

    @property
    @abstractmethod
    def audit_name(self) -> str:
        pass

    @property
    @abstractmethod
    def category(self) -> str:
        pass

    def setup(self) -> None:
        pass

    def before_execute(self) -> None:
        """Lifecycle hook before execution."""
        pass

    def after_execute(self) -> None:
        """Lifecycle hook after execution."""
        pass

    def cleanup(self) -> None:
        pass

    def register_record(self, count: int = 1) -> None:
        self.records_checked += count

    def register_check(self) -> None:
        self.checks_executed += 1

    def register_warning(self) -> None:
        self.warnings_generated += 1

    def add_finding(self, severity: Severity, title: str, description: str, evidence: Optional[Dict[str, Any]] = None) -> None:
        new_finding = Finding(
            audit_id=self.audit_id,
            audit=self.audit_name,
            severity=severity,
            title=title,
            description=description,
            evidence=evidence or {}
        )
        if new_finding.fingerprint not in self._finding_fingerprints:
            self._finding_fingerprints.add(new_finding.fingerprint)
            self.findings.append(new_finding)

    @abstractmethod
    def collect_findings(self) -> None:
        pass
