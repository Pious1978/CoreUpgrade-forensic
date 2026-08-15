"""
Real-Time Position Reconciliation Engine
"""

from typing import Dict, Any
from dataclasses import dataclass
from src.runtime.state import RuntimeStateController
from src.security.audit import ImmutableAuditLedger


@dataclass(frozen=True, slots=True)
class PositionState:
    symbol: str
    internal_quantity: float
    broker_quantity: float
    tolerance: float = 0.0001


class PositionReconciliationEngine:

    _internal_ledger: Dict[str, float] = {}

    @classmethod
    def record_internal_execution(cls, symbol: str, quantity_delta: float):
        """
        Updates internal position tracker upon order fill notification.
        """
        current = cls._internal_ledger.get(symbol, 0.0)
        cls._internal_ledger[symbol] = current + quantity_delta

    @classmethod
    def reconcile_broker_feed(cls, broker_report: Dict[str, Any]):
        """
        Reconciles broker execution report against internal ledger.
        Triggers immediate HALTED_FATAL if position mismatch is detected.
        """
        symbol = broker_report.get("symbol")
        broker_qty = float(broker_report.get("position_quantity", 0.0))

        if not symbol:
            raise RuntimeError("CRITICAL RECONCILIATION ERROR: Broker report missing symbol.")

        internal_qty = cls._internal_ledger.get(symbol, 0.0)
        discrepancy = abs(internal_qty - broker_qty)

        if discrepancy > 0.0001:
            error_msg = (
                f"POSITION DISCREPANCY DETECTED for {symbol}! "
                f"Internal Ledger: {internal_qty}, Broker Report: {broker_qty}, Discrepancy: {discrepancy}"
            )
            
            # 1. Audit Reservation & Commit
            res_id = ImmutableAuditLedger.reserve_event("RECONCILIATION_FAILURE", {
                "symbol": symbol,
                "internal_qty": internal_qty,
                "broker_qty": broker_qty,
                "discrepancy": discrepancy
            })
            ImmutableAuditLedger.commit_event(res_id, "COMMITTED")

            # 2. Trigger Hard System Halt
            RuntimeStateController.force_halt(
                fatal=True,
                reason=f"Position reconciliation failure on {symbol}."
            )
            
            raise RuntimeError(error_msg)