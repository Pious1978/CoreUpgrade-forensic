"""
Contract Capability

Defines runtime capability permissions governing access across downstream execution, 
portfolio, and audit engines.
"""

from enum import Enum


class ContractCapability(str, Enum):
    RESEARCH_READ = "research_read"
    GOVERNANCE_READ = "governance_read"
    PORTFOLIO_ENTRY = "portfolio_entry"
    EXECUTION = "execution"
