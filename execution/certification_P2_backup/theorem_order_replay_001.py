# execution/certification/theorem_order_replay_001.py
from typing import List
from execution.oms.order_manager import OrderRecord
from execution.contracts.order_event_record import OrderEventRecord

class OrderReplayTheorem:
    """
    THEOREM-ORDER-REPLAY-001 (v1.1.0)
    Invariant: Same Initial State + Same ExecutionEvent Stream 
    = Identical Final OrderRecord AND Identical State Transition Audit Trail.
    """
    id = "THEOREM-ORDER-REPLAY-001"
    version = "1.1.0"

    @classmethod
    def verify(
        cls,
        original_record: OrderRecord,
        replayed_record: OrderRecord,
        original_audit_log: List[OrderEventRecord],
        replayed_audit_log: List[OrderEventRecord]
    ) -> dict:
        
        # 1. Verify Endpoint Identity
        endpoints_identical = (original_record == replayed_record)
        
        # 2. Verify Complete Transition History Identity
        if len(original_audit_log) != len(replayed_audit_log):
            return {
                "certified": False,
                "reason": "Order replay divergence detected: Audit log length mismatch.",
                "original_log_len": len(original_audit_log),
                "replayed_log_len": len(replayed_audit_log)
            }

        history_identical = all(
            orig.record_hash == repl.record_hash 
            for orig, repl in zip(original_audit_log, replayed_audit_log)
        )

        if not endpoints_identical or not history_identical:
            return {
                "certified": False,
                "reason": "Order replay divergence detected in OMS state or audit trail history.",
                "endpoints_match": endpoints_identical,
                "history_match": history_identical
            }

        return {
            "certified": True,
            "reason": "Order replay successfully verified. Both final state and transition history match."
        }
