from dataclasses import dataclass
from .base import BaseContract, ContractType, TrustLevel

@dataclass(frozen=True)
class UniverseContract(BaseContract):
    contract_type: ContractType = ContractType.UNIVERSE  # Or register a new type if needed, or handle via metadata
    symbol: str = ""
    exchange: str = "NASDAQ"
    market_cap_category: str = "LARGE_CAP"
    sector: str = "Technology"
    liquidity_tier: str = "TIER_1"
    is_eligible: bool = True
