from oms.engine.order_management_engine import OrderManagementEngine
from event_store.memory_store import ImmutableEventStore

class DecisionReplayEngine:
    def __init__(self, event_store: ImmutableEventStore):
        self.event_store = event_store

    def replay_stream(self, aggregate_id: str) -> OrderManagementEngine:
        """
        Executes a pure, isolated replay by instantiating a fresh OrderManager 
        and replaying historical immutable events sequentially.
        """
        # Instantiate a fresh, isolated state container per replay pass
        order_manager = OrderManagementEngine()
        
        stream_events = self.event_store.get_stream(aggregate_id)
        
        for event in stream_events:
            order_manager.apply_event(event)

        return order_manager