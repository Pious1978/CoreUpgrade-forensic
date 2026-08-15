from enum import Enum


class AuditStatus(str, Enum):
    """Execution status of an audit module."""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"
