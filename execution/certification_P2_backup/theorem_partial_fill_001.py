# execution/certification/theorem_partial_fill_001.py
from datetime import datetime
from decimal import Decimal
from execution.contracts.order_contract import OrderIntent
from execution.contracts.execution_event import ExecutionEvent
from execution.replay.replay_engine import ReplayEngine

class PartialFillTheorem:
    id = "THEOREM-PARTIAL-FILL-001"
    version = "1.0.0"

    @classmethod
    def verify(cls) -> dict:
        intent = OrderIntent(
            order_id="ORD-PF-001", intent_id="INT-PF-001", portfolio_id="PORT-001",
            instrument_id="AMZN", side="BUY", quantity=Decimal("100"), order_type="LIMIT",
            limit_price=Decimal("100.00"), exchange="NASDAQ", timestamp=datetime(2026, 6, 1, 12, 0, 0)
        )
        # Sequential partial fills: 40 @ 100, 30 @ 102, 30 @ 98 -> Total 100 shares, expected avg price 100.00
        events = [
            ExecutionEvent(
                event_id="EVT-PF-1", order_id="ORD-PF-001", intent_id="INT-PF-001",
                event_type="PARTIAL_FILL", fill_price=Decimal("100.00"), fill_quantity=Decimal("40"),
                remaining_quantity=Decimal("60"), timestamp=datetime(2026, 6, 1, 12, 1, 0), raw_message="PF1"
            ),
            ExecutionEvent(
                event_id="EVT-PF-2", order_id="ORD-PF-001", intent_id="INT-PF-001",
                event_type="PARTIAL_FILL", fill_price=Decimal("102.00"), fill_quantity=Decimal("30"),
                remaining_quantity=Decimal("30"), timestamp=datetime(2026, 6, 1, 12, 2, 0), raw_message="PF2"
            ),
            ExecutionEvent(
                event_id="EVT-PF-3", order_id="ORD-PF-001", intent_id="INT-PF-001",
                event_type="FULL_FILL", fill_price=Decimal("98.00"), fill_quantity=Decimal("30"),
                remaining_quantity=Decimal("0"), timestamp=datetime(2026, 6, 1, 12, 3, 0), raw_message="FF3"
            ),
        ]

        engine = ReplayEngine([intent])
        positions, _ = engine.replay(events, initial_cash=Decimal("50000.00"))

        amzn_pos = positions.get("AMZN")
        if not amzn_pos or amzn_pos.quantity != Decimal("100"):
            return {"certified": False, "reason": f"Partial fill quantity accumulation failed. Got: {amzn_pos}"}

        # Expected total cost = (40*100) + (30*102) + (30*98) = 4000 + 3060 + 2940 = 10000 -> Avg price 100.00
        if amzn_pos.average_price != Decimal("100.00"):
            return {"certified": False, "reason": f"Partial fill average price calculation incorrect. Got: {amzn_pos.average_price}"}

        return {"certified": True, "reason": "Partial fill quantity accumulation and average price weighting verified."}