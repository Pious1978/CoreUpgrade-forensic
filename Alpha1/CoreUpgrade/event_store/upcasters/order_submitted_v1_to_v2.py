from typing import Dict
from event_store.schema_registry import EventSchemaRegistry

def upcast_order_submitted_v1_to_v2(payload: Dict) -> Dict:
    """Upcasts OrderSubmittedEvent by injecting a default exchange venue for legacy events."""
    # Create a new dict to avoid mutating shared state unexpectedly
    new_payload = dict(payload)
    
    # Legacy orders predating this schema change were strictly NSE
    new_payload["exchange_venue"] = "NSE_LEGACY" 
    
    return new_payload

EventSchemaRegistry.register_upcaster("OrderSubmittedEvent", 1, upcast_order_submitted_v1_to_v2)
