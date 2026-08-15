from execution.certification.contracts.empirical_theorem import EmpiricalTheorem
# execution/certification/theorem_event_order_consistency_001.py
from execution.contracts.execution_event import ExecutionEvent

class EventOrderConsistencyTheorem(EmpiricalTheorem):
    """
    THEOREM-EVENT-ORDER-CONSISTENCY-001

    Invariant:
    Every execution event must map exactly to
    the order and intent lineage it claims to modify.
    """

    id = "THEOREM-EVENT-ORDER-CONSISTENCY-001"
    version = "1.0.0"

    @classmethod
    def verify(
        cls,
        event: ExecutionEvent,
        order_id: str,
        intent_id: str
    ) -> dict:

        if event.order_id != order_id:
            return {
                "certified": False,
                "reason": "Execution event order lineage mismatch."
            }

        if event.intent_id != intent_id:
            return {
                "certified": False,
                "reason": "Execution event intent lineage mismatch."
            }

        return {
            "certified": True,
            "reason": None
        }

