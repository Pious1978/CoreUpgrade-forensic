from typing import Callable, Dict, Type

from oms.events.base import BaseOrderEvent
from oms.events.execution import (
    OrderExecutionErrorEvent,
    OrderRejectedEvent,
    OrderSubmittedEvent,
    OrderTransitionEvent,
)
from oms.events.risk import OrderAcceptedEvent, RiskRejectedEvent


def upcast_order_submitted_v1_to_v2(payload: Dict) -> Dict:
    """Defensive migration for OrderSubmittedEvent v1 -> v2."""
    new_payload = dict(payload)
    # setdefault ensures we do not overwrite data if the payload was partially migrated
    new_payload.setdefault("exchange_venue", "NSE_LEGACY")
    return new_payload


class EventSchemaRegistry:
    """Manages event class mapping and historical payload upcasting chains."""

    _CLASS_MAP: Dict[str, Type[BaseOrderEvent]] = {
        "RiskRejectedEvent": RiskRejectedEvent,
        "OrderAcceptedEvent": OrderAcceptedEvent,
        "OrderSubmittedEvent": OrderSubmittedEvent,
        "OrderTransitionEvent": OrderTransitionEvent,
        "OrderRejectedEvent": OrderRejectedEvent,
        "OrderExecutionErrorEvent": OrderExecutionErrorEvent,
    }

    # Maps (event_type, from_version) -> Upcaster Function
    _UPCASTERS: Dict[tuple[str, int], Callable[[Dict], Dict]] = {}

    @classmethod
    def register_upcaster(cls, event_type: str, from_version: int, upcaster_func: Callable[[Dict], Dict]) -> None:
        cls._UPCASTERS[(event_type, from_version)] = upcaster_func

    @classmethod
    def get_event_class(cls, event_type: str) -> Type[BaseOrderEvent]:
        if event_type not in cls._CLASS_MAP:
            raise ValueError(f"Unregistered event type: {event_type}")
        return cls._CLASS_MAP[event_type]

    @classmethod
    def get_target_version(cls, event_type: str) -> int:
        """Dynamically extracts the current schema version from the dataclass."""
        event_class = cls.get_event_class(event_type)
        return getattr(event_class, "SCHEMA_VERSION", 1)

    @classmethod
    def upcast(cls, event_type: str, payload_version: int, payload: Dict, target_version: int) -> Dict:
        """Applies a sequential chain of upcasters to modernize a historical payload."""
        current_version = payload_version

        while current_version < target_version:
            transformer = cls._UPCASTERS.get((event_type, current_version))
            if not transformer:
                raise ValueError(
                    f"Missing upcaster for {event_type} migrating from v{current_version} to v{current_version + 1}"
                )
            payload = transformer(payload)
            current_version += 1

        return payload

# Register known upcasters on module load
EventSchemaRegistry.register_upcaster("OrderSubmittedEvent", 1, upcast_order_submitted_v1_to_v2)
