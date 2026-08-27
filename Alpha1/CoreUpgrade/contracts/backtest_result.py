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
    BACKTEST_RESULT = "BacktestResultContract"

@dataclass(frozen=True)
class BacktestResultContract(BaseContract):
    contract_type: ContractType = ContractType.BACKTEST_RESULT
    strategy_id: str = ""
    train_period: str = ""
    validation_period: str = ""
    cagr: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    alpha: float = 0.0
    beta: float = 1.0
    information_ratio: float = 0.0
    market_regime: str = "BULL"
    promotion_status: str = "REJECTED"
