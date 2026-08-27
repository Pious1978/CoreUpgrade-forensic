"""
Trust Level

Defines the security and verification tiers associated with platform contracts, 
separating scientific validity, governance certification, and execution authorization.
"""

from enum import Enum


class TrustLevel(str, Enum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    GOVERNANCE_CERTIFIED = "governance_certified"
    EXECUTION_AUTHORIZED = "execution_authorized"
