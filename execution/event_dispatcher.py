import logging
from typing import Callable, List, Any

logger = logging.getLogger(__name__)

class ExecutionEventDispatcher:
    """
    Decouples event generation from the execution gateway. 
    Handles persistence into the core VSC Event Store and broadcasts 
    lifecycle events to registered system listeners (telemetry, dashboards).
    """
    def __init__(self, event_store=None):
        self.event_store = event_store
        self._listeners: List[Callable[[Any], None]] = []

    def register_listener(self, listener: Callable[[Any], None]) -> None:
        """Registers a callback function to listen to execution and order events."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def dispatch(self, event: Any) -> None:
        """
        Dispatches an immutable event to the persistent event store 
        and fans it out to all registered system listeners.
        """
        event_name = type(event).__name__

        # 1. Persist to central VSC Event Store
        if self.event_store is not None:
            if hasattr(self.event_store, "append"):
                try:
                    self.event_store.append(event)
                except Exception as ex:
                    logger.error(f"Critical: Failed to append {event_name} to event store: {ex}")
                    raise
            else:
                raise AttributeError("Provided event_store object does not implement an 'append' method.")

        # 2. Broadcast to registered listeners (Dashboards, WebSocket feeds, Metrics)
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as ex:
                listener_name = getattr(listener, "__name__", "anonymous_listener")
                logger.error(f"Error in execution event listener '{listener_name}' while handling {event_name}: {ex}")
