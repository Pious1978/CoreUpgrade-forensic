# execution/reconciliation/cash_reconciler.py
"""
Cash Reconciliation Engine

Authority:
    Execution Layer

Purpose:
    Compare reconstructed OMS cash and margin state against external broker feed 
    using the canonical CashSnapshot contract.

Restrictions:
    - Does not mutate OMS state
    - Does not write to EventStore
    - Does not create corrective trades
    - Only produces reconciliation evidence
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

from execution.contracts.cash_snapshot import CashSnapshot

@dataclass(frozen=True)
class CashMismatch:
    currency: str
    expected_available_cash: Decimal
    actual_available_cash: Decimal
    available_cash_delta: Decimal
    expected_margin_used: Decimal
    actual_margin_used: Decimal
    margin_used_delta: Decimal

@dataclass(frozen=True)
class CashReconciliationReport:
    matched: bool
    mismatches: tuple[CashMismatch, ...]

class CashReconciler:
    """
    Deterministic comparison engine between:

    Expected:
        OMS replay state (canonical CashSnapshot)

    Actual:
        Broker-supplied cash and margin feed
    """

    def reconcile(
        self,
        expected_cash: Mapping[str, CashSnapshot],
        broker_cash: Mapping[str, CashSnapshot],
    ) -> CashReconciliationReport:

        currencies = (
            set(expected_cash.keys())
            |
            set(broker_cash.keys())
        )

        mismatches = []

        for currency in sorted(currencies):

            expected = expected_cash.get(
                currency,
                CashSnapshot(
                    currency=currency,
                    available_cash=Decimal("0"),
                    settled_cash=Decimal("0"),
                    unsettled_cash=Decimal("0"),
                    margin_used=Decimal("0"),
                    buying_power=Decimal("0"),
                ),
            )

            actual = broker_cash.get(
                currency,
                CashSnapshot(
                    currency=currency,
                    available_cash=Decimal("0"),
                    settled_cash=Decimal("0"),
                    unsettled_cash=Decimal("0"),
                    margin_used=Decimal("0"),
                    buying_power=Decimal("0"),
                ),
            )

            available_cash_delta = (
                actual.available_cash
                -
                expected.available_cash
            )

            margin_used_delta = (
                actual.margin_used
                -
                expected.margin_used
            )

            if available_cash_delta != Decimal("0") or margin_used_delta != Decimal("0"):

                mismatches.append(
                    CashMismatch(
                        currency=currency,
                        expected_available_cash=expected.available_cash,
                        actual_available_cash=actual.available_cash,
                        available_cash_delta=available_cash_delta,
                        expected_margin_used=expected.margin_used,
                        actual_margin_used=actual.margin_used,
                        margin_used_delta=margin_used_delta,
                    )
                )

        return CashReconciliationReport(
            matched=len(mismatches) == 0,
            mismatches=tuple(mismatches),
        )