# execution/contracts/cash_snapshot.py
"""
Canonical Cash Snapshot Contract

Authority:
    Execution Layer Contracts

Purpose:
    Defines the canonical representation of cash, settled balances, 
    margin utilization, and buying power shared across replayers, 
    reconcilers, OMS projections, and broker adapters.

Restrictions:
    - Immutable dataclass
    - No business logic or state modification
"""
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class CashSnapshot:
    """
    Standardized, multi-dimensional cash and margin state descriptor.
    """
    currency: str
    available_cash: Decimal
    settled_cash: Decimal
    unsettled_cash: Decimal
    margin_used: Decimal
    buying_power: Decimal