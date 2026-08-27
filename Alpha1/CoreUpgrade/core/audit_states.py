from enum import Enum


class AuditExecutionState(str, Enum):
    """Versioned lifecycle state constants for audit execution."""
    INITIALIZED = "INITIALIZED"
    VALIDATING = "VALIDATING"
    BLOCKED = "BLOCKED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CLEANUP = "CLEANUP"
    CANCELLED = "CANCELLED"
