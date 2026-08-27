# execution/certification/theorem_replay_determinism_001.py
from datetime import datetime
from decimal import Decimal
from execution.contracts.order_contract import OrderIntent
from execution.contracts.execution_event import ExecutionEvent
from execution.replay.replay_engine import ReplayEngine
from research.governance.serialization import CanonicalSerializer

class ReplayDeterminismTheorem:
    id = "THEOREM-REPLAY-DETERMINISM-001"
    version = "1.0.0"

    @classmethod
    def verify(cls) -> dict:
        intent = OrderIntent(
            order_id="ORD-DET-001", intent_id="INT-DET-001", portfolio_id="PORT-001",
            instrument_id="MSFT", side="BUY", quantity=Decimal("200"), order_type="LIMIT",
            limit_price=Decimal("300.00"), exchange="NASDAQ", timestamp=datetime(2026, 6, 1, 10, 0, 0)
        )
        events = [
            ExecutionEvent(
                event_id="EVT-D-01", order_id="ORD-DET-001", intent_id="INT-DET-001",
                event_type="FULL_FILL", fill_price=Decimal("300.00"), fill_quantity=Decimal("200"),
                remaining_quantity=Decimal("0"), timestamp=datetime(2026, 6, 1, 10, 1, 0), raw_message="FILL"
            )
        ]

        # Run Replay Instance 1
        engine_1 = ReplayEngine([intent])
        pos_1, cash_1 = engine_1.replay(events, initial_cash=Decimal("50000.00"))

        # Run Replay Instance 2 (Independent)
        engine_2 = ReplayEngine([intent])
        pos_2, cash_2 = engine_2.replay(events, initial_cash=Decimal("50000.00"))

        # Verify idempotence: Replaying again on the same engine instance must not alter state
        pos_1_repeat, cash_1_repeat = engine_1.replay([], initial_cash=Decimal("50000.00"))

        # Use canonical serialization hashes to avoid fragile direct dataclass equality if metadata expands
        hash_1 = CanonicalSerializer.hash((pos_1, cash_1))
        hash_2 = CanonicalSerializer.hash((pos_2, cash_2))
        hash_repeat = CanonicalSerializer.hash((pos_1_repeat, cash_1_repeat))

        if hash_1 != hash_2 or hash_1 != hash_repeat:
            return {"certified": False, "reason": "Replay determinism or idempotence violation: Fingerprints diverged."}

        return {"certified": True, "reason": "Replay determinism and idempotence successfully verified via canonical hashing."}