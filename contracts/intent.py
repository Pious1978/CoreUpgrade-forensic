from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from .base_contract import BaseContract


class ContractType(Enum):
    PORTFOLIO_INTENT = "MultiAssetPortfolioIntentContract"


@dataclass(frozen=True)
class MultiAssetPortfolioIntentContract(BaseContract):
    contract_type: ContractType = ContractType.PORTFOLIO_INTENT
    portfolio_id: str = "DEFAULT"
    target_allocations: Mapping[str, float] = field(default_factory=dict)
    cash_target_weight: float = 0.0
    expected_portfolio_volatility: float = 0.0