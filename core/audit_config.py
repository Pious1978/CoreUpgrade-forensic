from dataclasses import dataclass, field
from typing import Set


@dataclass(frozen=True)
class FailurePolicy:
    """Institutional rules governing whether pipeline failures block execution."""
    fail_fast: bool = True
    blocking_categories: Set[str] = field(
        default_factory=lambda: {"database", "schema", "security"}
    )


@dataclass(frozen=True)
class AuditConfig:
    """Central configuration for the framework and business failure policies."""
    environment: str = "production"
    timeout_seconds: float = 300.0
    failure_policy: FailurePolicy = field(default_factory=FailurePolicy)
    strict_mode: bool = True
