# execution/certification/theorem_reconciliation_purity_001.py
import copy
from decimal import Decimal
from execution.reconciliation.position_reconciler import PositionReconciler, PositionSnapshot
from execution.reconciliation.cash_reconciler import CashReconciler
from execution.contracts.cash_snapshot import CashSnapshot

class ReconciliationPurityTheorem:
    id = "THEOREM-RECONCILIATION-PURITY-001"
    version = "1.0.0"

    @classmethod
    def verify(cls) -> dict:
        pos_snapshot = PositionSnapshot(symbol="AAPL", quantity=Decimal("50"), average_price=Decimal("150.00"))
        cash_snapshot = CashSnapshot(currency="USD", available_cash=Decimal("1000.00"), settled_cash=Decimal("1000.00"), unsettled_cash=Decimal("0"), margin_used=Decimal("0"), buying_power=Decimal("1000.00"))

        pos_input = {"AAPL": pos_snapshot}
        cash_input = {"USD": cash_snapshot}

        pos_input_deep_copy = copy.deepcopy(pos_input)
        cash_input_deep_copy = copy.deepcopy(cash_input)

        pos_reconciler = PositionReconciler()
        cash_reconciler = CashReconciler()

        # Run reconciliation twice to check report consistency
        report_p1 = pos_reconciler.reconcile(pos_input, pos_input)
        report_p2 = pos_reconciler.reconcile(pos_input, pos_input)

        report_c1 = cash_reconciler.reconcile(cash_input, cash_input)
        report_c2 = cash_reconciler.reconcile(cash_input, cash_input)

        # Check input mutation protection
        inputs_unmodified = (pos_input == pos_input_deep_copy) and (cash_input == cash_input_deep_copy)
        reports_consistent = (report_p1 == report_p2) and (report_c1 == report_c2) and report_p1.matched and report_c1.matched

        if not inputs_unmodified:
            return {"certified": False, "reason": "Reconciliation mutation violation: Input snapshots were altered during execution."}
        if not reports_consistent:
            return {"certified": False, "reason": "Reconciliation determinism violation: Successive report runs diverged."}

        return {"certified": True, "reason": "Reconciliation zero-mutation input purity and report consistency verified."}