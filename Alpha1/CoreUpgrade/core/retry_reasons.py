from enum import Enum


class RetryReason(str, Enum):
    """Categorized enterprise retry reasons for SIEM and dashboard analytics."""
    TRANSIENT = "TRANSIENT"
    DEPENDENCY = "DEPENDENCY"
    TIMEOUT = "TIMEOUT"
    NETWORK = "NETWORK"
    RATE_LIMIT = "RATE_LIMIT"
    LOCK_CONTENTION = "LOCK_CONTENTION"
    UNKNOWN = "UNKNOWN"
