from dataclasses import dataclass
from enum import Enum

from .base_contract import BaseContract


class ContractType(Enum):
    UNIVERSE = "UniverseContract"


@dataclass(frozen=True)
class UniverseContract(BaseContract):
    contract_type: ContractType = ContractType.UNIVERSE
    symbol: str = ""
    exchange: str = "NASDAQ"
    market_cap_category: str = "LARGE_CAP"
    sector: str = "Technology"
    liquidity_tier: str = "TIER_1"
    is_eligible: bool = True