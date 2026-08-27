"""
Position Reconciliation Engine

Authority:
    Execution Layer

Purpose:
    Compare reconstructed OMS state against external broker state.

Restrictions:
    - Does not mutate OMS state
    - Does not write to EventStore
    - Does not create corrective trades
    - Only produces reconciliation evidence
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping


@dataclass(frozen=True)
class PositionSnapshot:
    symbol: str
    quantity: Decimal
    average_price: Decimal


@dataclass(frozen=True)
class PositionMismatch:
    symbol: str
    expected_quantity: Decimal
    actual_quantity: Decimal
    quantity_delta: Decimal


@dataclass(frozen=True)
class ReconciliationReport:
    matched: bool
    mismatches: tuple[PositionMismatch, ...]



class PositionReconciler:
    """
    Deterministic comparison engine between:

    Expected:
        OMS replay state

    Actual:
        Broker supplied positions
    """

    def reconcile(
        self,
        expected_positions: Mapping[str, PositionSnapshot],
        broker_positions: Mapping[str, PositionSnapshot],
    ) -> ReconciliationReport:

        symbols = (
            set(expected_positions.keys())
            |
            set(broker_positions.keys())
        )

        mismatches = []

        for symbol in sorted(symbols):

            expected = expected_positions.get(
                symbol,
                PositionSnapshot(
                    symbol=symbol,
                    quantity=Decimal("0"),
                    average_price=Decimal("0"),
                ),
            )

            actual = broker_positions.get(
                symbol,
                PositionSnapshot(
                    symbol=symbol,
                    quantity=Decimal("0"),
                    average_price=Decimal("0"),
                ),
            )

            delta = (
                actual.quantity
                -
                expected.quantity
            )

            if delta != Decimal("0"):

                mismatches.append(
                    PositionMismatch(
                        symbol=symbol,
                        expected_quantity=expected.quantity,
                        actual_quantity=actual.quantity,
                        quantity_delta=delta,
                    )
                )

        return ReconciliationReport(
            matched=len(mismatches) == 0,
            mismatches=tuple(mismatches),
        )