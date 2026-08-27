# portfolio/projections/portfolio_projection.py

from replay.models import Projection
from oms.events.base import BaseOrderEvent
from portfolio.projections.portfolio_projector import PortfolioProjector
from portfolio.models.portfolio_state import PortfolioState

class PortfolioProjection(Projection):
    """Stateful wrapper satisfying the Replay Protocol."""
    
    def __init__(self, initial_state: PortfolioState):
        self._state = initial_state
        self._intent_cache = {} 

    def apply(self, event: BaseOrderEvent) -> None:
        # Example cache build
        if type(event).__name__ == "OrderAcceptedEvent":
            self._intent_cache[event.intent_id] = event 
            
        intent = self._intent_cache.get(event.intent_id)
        if intent:
            # Re-assign state purely by calling the stateless Projector
            self._state = PortfolioProjector.apply(self._state, intent, event)

    def snapshot(self) -> PortfolioState:
        return self._state
