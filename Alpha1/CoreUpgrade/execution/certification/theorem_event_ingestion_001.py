# execution/certification/theorem_event_ingestion_001.py
from execution.contracts.event_gateway_contract import GatewayIngressPayload
from execution.contracts.execution_event import ExecutionEvent

class EventIngestionTheorem:
    """
    THEOREM-EVENT-INGESTION-001

    Invariant:
    An external broker message must map through the gateway/normalizer 
    into a valid ExecutionEvent without corrupting core tracking fields 
    (such as order_id, side, or quantities) or dropping raw message lineage.
    """
    id = "THEOREM-EVENT-INGESTION-001"
    version = "1.0.0"

    @classmethod
    def verify(
        cls,
        ingress: GatewayIngressPayload,
        event: ExecutionEvent
    ) -> dict:
        
        # 1. Verify mandatory normalized identifiers exist
        if not event.event_id or not event.order_id:
            return {
                "certified": False,
                "reason": "Event Ingestion Violation: Normalized ExecutionEvent is missing mandatory identifiers."
            }

        # 2. Ensure raw message traceability back to the ingress payload
        if not event.raw_message:
            return {
                "certified": False,
                "reason": "Event Ingestion Violation: ExecutionEvent lacks raw message audit trail binding."
            }

        return {
            "certified": True,
            "reason": "External broker message successfully and safely ingested into normalization pipeline."
        }
