from dataclasses import dataclass, field
from typing import Mapping, List
from .base import BaseContract, ContractType

@dataclass(frozen=True)
class MultiAssetPortfolioIntentContract(BaseContract):
    contract_type: ContractType = ContractType.PORTFOLIO_INTENT
    portfolio_id: str = "DEFAULT"
    target_allocations: Mapping[str, float] = field(default_factory=dict)
    cash_target_weight: float = 0.0
    expected_portfolio_volatility: float = 0.0
