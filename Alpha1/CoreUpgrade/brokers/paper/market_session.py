from enum import Enum
from dataclasses import dataclass

class MarketSessionState(Enum):
    PRE_OPEN = "PRE_OPEN"
    REGULAR = "REGULAR"
    POST_CLOSE = "POST_CLOSE"
    CLOSED = "CLOSED"
    HALTED = "HALTED"

@dataclass(frozen=True)
class SessionDecision:
    can_execute: bool
    queue_order: bool
    reason: str | None

class MarketSessionEngine:
    def __init__(self, override_state: MarketSessionState = None):
        self.override_state = override_state

    def evaluate_session(self, order) -> SessionDecision:
        state = self.override_state if self.override_state else MarketSessionState.REGULAR
        
        if state == MarketSessionState.REGULAR:
            return SessionDecision(can_execute=True, queue_order=False, reason=None)
        elif state == MarketSessionState.PRE_OPEN:
            return SessionDecision(can_execute=False, queue_order=True, reason="PRE_OPEN_QUEUED")
        elif state == MarketSessionState.CLOSED:
            return SessionDecision(can_execute=False, queue_order=False, reason="MARKET_CLOSED")
        elif state == MarketSessionState.HALTED:
            return SessionDecision(can_execute=False, queue_order=False, reason="MARKET_HALTED")
        
        return SessionDecision(can_execute=False, queue_order=False, reason=f"UNKNOWN_SESSION_{state.value}")
