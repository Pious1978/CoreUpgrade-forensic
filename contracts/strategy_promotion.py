from dataclasses import dataclass, field
from uuid import UUID, uuid4
from datetime import datetime, timezone
from enum import Enum

try:
    from contracts.base_contract import BaseContract
except ImportError:
    @dataclass(frozen=True)
    class BaseContract:
        immutable_id: UUID = field(default_factory=uuid4)
        root_contract_id: UUID = field(default_factory=uuid4)
        correlation_id: UUID = field(default_factory=uuid4)
        created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class ContractType(Enum):
    STRATEGY_PROMOTION = "StrategyPromotionContract"

@dataclass(frozen=True)
class StrategyPromotionContract(BaseContract):
    contract_type: ContractType = ContractType.STRATEGY_PROMOTION
    strategy_id: str = ""
    version: str = "1.0"
    experiment_id: str = ""
    dataset_version: str = "DEFAULT_V1"
    validation_period: str = ""
    cagr: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    alpha: float = 0.0
    promotion_status: str = "REJECTED"
    approved_by_policy: bool = False
