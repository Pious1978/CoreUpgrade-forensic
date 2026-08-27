from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass(frozen=True)
class PositionWeight:
    symbol: str
    weight: float

@dataclass(frozen=True)
class TradeInstruction:
    symbol: str
    target_shares: float
    target_weight: float
    limit_price: Optional[float] = None

@dataclass(frozen=True)
class ExecutionFill:
    fill_id: str
    symbol: str
    shares: float
    price: float
    timestamp: datetime
    venue: str
    commission: float

@dataclass(frozen=True)
class PolicyFinding:
    policy_id: str
    rule_name: str
    status: str
    message: str
    severity: str

@dataclass(frozen=True)
class ComplianceFinding:
    rule_id: str
    rule_name: str
    status: str
    details: str

@dataclass(frozen=True)
class KillSwitchFinding:
    trigger_name: str
    triggered: bool
    priority: str
    reason: str
