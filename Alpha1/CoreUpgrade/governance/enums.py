from enum import Enum
class GovernanceDecisionType(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
class GovernanceActionType(Enum):
    HALT = "halt"
    PROCEED = "proceed"
