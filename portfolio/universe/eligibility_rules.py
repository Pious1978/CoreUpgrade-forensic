# portfolio/universe/eligibility_rules.py
import dataclasses
from abc import ABC, abstractmethod
from typing import Tuple, Any
from portfolio.universe.metadata_provider import PointInTimeMetadata
from portfolio.contracts.asset_contract import AssetIdentity

@dataclasses.dataclass(frozen=True)
class FilterIdentity:
    filter_id: str
    version: str
    implementation_hash: str
    parameters: Tuple[Tuple[str, Any], ...]

class UniverseFilter(ABC):
    @property
    @abstractmethod
    def identity(self) -> FilterIdentity: pass

    @abstractmethod
    def evaluate(self, asset: AssetIdentity, metadata: PointInTimeMetadata) -> bool: pass

# Example Implementation
class MinLiquidityFilter(UniverseFilter):
    def __init__(self, min_adv_usd: Decimal):
        self._min_adv = min_adv_usd
        self._identity = FilterIdentity(
            filter_id="FILTER-LIQUIDITY-MIN-ADV",
            version="1.0.0",
            implementation_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            parameters=(("min_adv_usd", str(min_adv_usd)),)
        )
        
    @property
    def identity(self) -> FilterIdentity: return self._identity

    def evaluate(self, asset: AssetIdentity, metadata: PointInTimeMetadata) -> bool:
        return metadata.get_adv_30d(asset) >= self._min_adv
