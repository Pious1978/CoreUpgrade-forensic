from typing import Callable, Dict, List, Any

class EventBus:
    """Internal pub/sub event bus for decoupled framework lifecycle broadcasting."""

    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, callback: Callable) -> None:
        self._listeners.setdefault(event_type, []).append(callback)

    def publish(self, event_type: str, payload: Any = None) -> None:
        for callback in self._listeners.get(event_type, []):
            try:
                callback(payload)
            except Exception:
                pass

event_bus = EventBus()
