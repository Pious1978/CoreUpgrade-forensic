# portfolio/risk/providers/price_history_provider.py
import dataclasses
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Tuple
from portfolio.contracts.asset_contract import AssetIdentity

@dataclasses.dataclass(frozen=True)
class PriceObservation:
    instrument_id: str
    timestamp: datetime
    adjusted_close: Decimal

class PointInTimePriceHistory(ABC):
    @property
    @abstractmethod
    def snapshot_hash(self) -> str:
        """Cryptographic identity of the historical price database state."""
        pass
        
    @property
    @abstractmethod
    def max_available_time(self) -> datetime:
        """The latest timestamp this provider is currently authorized to expose."""
        pass

    @abstractmethod
    def get_returns_panel(
        self, 
        assets: Tuple[AssetIdentity, ...], 
        end_time: datetime, 
        lookback_days: int
    ) -> Tuple[PriceObservation, ...]:
        pass

# portfolio/risk/providers/factor_provider.py
class PointInTimeFactorProvider(ABC):
    @property
    @abstractmethod
    def snapshot_hash(self) -> str: pass
    
    @abstractmethod
    def get_exposures(
        self, 
        assets: Tuple[AssetIdentity, ...], 
        timestamp: datetime
    ) -> Tuple[dict, ...]: 
        pass
