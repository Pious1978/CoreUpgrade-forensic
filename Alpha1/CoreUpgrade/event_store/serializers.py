import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from typing import Tuple

from event_store.schema_registry import EventSchemaRegistry
from oms.events.base import BaseOrderEvent
from oms.state_machine.order_state_machine import OrderState


class EventSerializer:
    """Explicit serialization boundary generating tamper-evident payloads and managing rehydration."""

    @staticmethod
    def serialize(event: BaseOrderEvent) -> Tuple[str, int, str, str]:
        """Returns: (event_type, schema_version, payload_json, payload_hash)"""
        event_type = event.__class__.__name__
        # Pull the version directly from the dataclass metadata
        schema_version = getattr(event.__class__, "SCHEMA_VERSION", 1)

        raw_dict = asdict(event)
        for key, value in raw_dict.items():
            if isinstance(value, datetime):
                raw_dict[key] = value.isoformat()
            elif isinstance(value, Decimal):
                raw_dict[key] = str(value)
            elif isinstance(value, OrderState):
                raw_dict[key] = value.value

        payload = json.dumps(raw_dict, sort_keys=True)
        payload_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest()

        return event_type, schema_version, payload, payload_hash

    @staticmethod
    def deserialize(event_type: str, schema_version: int, payload_str: str) -> BaseOrderEvent:
        """Upcasts historical payloads and reconstructs the modern dataclass."""
        event_class = EventSchemaRegistry.get_event_class(event_type)
        target_version = EventSchemaRegistry.get_target_version(event_type)
        
        raw_dict = json.loads(payload_str)

        # 1. CHAINED UPCAST (Migrate historical schema to current schema)
        if schema_version < target_version:
            raw_dict = EventSchemaRegistry.upcast(event_type, schema_version, raw_dict, target_version)

        # 2. STRICT TYPE MAPPING (JSON primitives -> Domain primitives)
        if "timestamp" in raw_dict:
            raw_dict["timestamp"] = datetime.fromisoformat(raw_dict["timestamp"])
        
        if event_class.__name__ == "OrderTransitionEvent":
            raw_dict["from_state"] = OrderState(raw_dict["from_state"])
            raw_dict["to_state"] = OrderState(raw_dict["to_state"])
            raw_dict["filled_quantity"] = Decimal(raw_dict["filled_quantity"])
            raw_dict["remaining_quantity"] = Decimal(raw_dict["remaining_quantity"])
            if raw_dict.get("average_fill_price"):
                raw_dict["average_fill_price"] = Decimal(raw_dict["average_fill_price"])

        return event_class(**raw_dict)
