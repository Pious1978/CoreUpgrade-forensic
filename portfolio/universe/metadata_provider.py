# portfolio/universe/metadata_provider.py
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Tuple
from portfolio.contracts.asset_contract import AssetIdentity

class PointInTimeBasePopulation(ABC):
    """
    Prevents Survivorship Bias. 
    Never uses a modern static list (e.g., "Today's NIFTY 500").
    Returns the exact set of legal entities that existed on the given date.
    """
    @property
    @abstractmethod
    def population_id(self) -> str: pass
    
    @abstractmethod
    def members_at(self, timestamp: str) -> Tuple[AssetIdentity, ...]: pass

class PointInTimeMetadata(ABC):
    """
    Provides T-0 metadata. Strict Decimal enforcement prevents floating-point drift.
    """
    @property
    @abstractmethod
    def snapshot_hash(self) -> str:
        """Cryptographic identity of the underlying data state (provenance)."""
        pass
        
    @abstractmethod
    def get_market_cap(self, asset: AssetIdentity) -> Decimal: pass
    
    @abstractmethod
    def get_adv_30d(self, asset: AssetIdentity) -> Decimal: pass
    
    @abstractmethod
    def is_delisted(self, asset: AssetIdentity) -> bool: pass
    
    @abstractmethod
    def is_halted(self, asset: AssetIdentity) -> bool: pass
