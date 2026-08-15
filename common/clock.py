from datetime import datetime
from typing import Protocol

class Clock(Protocol):
    """Protocol for deterministic time injection."""
    def now(self) -> datetime:
        ...
