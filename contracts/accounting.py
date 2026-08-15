from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4
from contracts.base_contract import BaseContract

class ContractType(Enum):
    EXECUTION_RESULT = "ExecutionResultContract"
    PORTFOLIO_ACCOUNTING = "PortfolioAccounting"

@dataclass(frozen=True)
class TradeFillContract(BaseContract):
    contract_type: ContractType = ContractType.EXECUTION_RESULT
    trade_id: UUID = field(default_factory=uuid4)
    symbol: str = ""
    side: str = "BUY"  # BUY / SELL
    quantity: float = 0.0
    fill_price: float = 0.0
    fees: float = 0.0

@dataclass(frozen=True)
class PortfolioLedgerEntry:
    entry_id: UUID = field(default_factory=uuid4)
    portfolio_id: str = ""
    symbol: str = ""
    transaction_type: str = ""  # BUY, SELL, FEE
    quantity_change: float = 0.0
    cash_change: float = 0.0
    reference_trade_id: UUID = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
