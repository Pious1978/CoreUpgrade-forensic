"""
Contract State

Defines the formal progression states for platform contracts across 
the decision lineage and execution pipeline, including terminal branch states.
"""

from enum import Enum


class ContractState(str, Enum):
    CREATED = "created"
    VALIDATED = "validated"
    GOVERNANCE_APPROVED = "governance_approved"
    PORTFOLIO_ELIGIBLE = "portfolio_eligible"
    EXECUTED = "executed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"
