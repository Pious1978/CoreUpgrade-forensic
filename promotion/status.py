from enum import Enum

class PromotionStatus(Enum):
    """Explicit promotion execution lifecycle states."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    VALIDATING = "VALIDATING"
    COMMITTED = "COMMITTED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"
    DEAD_LETTERED = "DEAD_LETTERED"
