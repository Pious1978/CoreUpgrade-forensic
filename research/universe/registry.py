from dataclasses import dataclass
from typing import Dict

@dataclass(frozen=True)
class UniverseAsset:
    symbol: str
    exchange: str
    sector: str
    market_cap_billions: float
    is_active: bool

class InvestmentUniverseRegistry:
    def __init__(self):
        # Governed institutional whitelist
        self._registry: Dict[str, UniverseAsset] = {
            "NVDA": UniverseAsset("NVDA", "NASDAQ", "Semiconductors", 3000.0, True),
            "AAPL": UniverseAsset("AAPL", "NASDAQ", "Consumer Electronics", 3500.0, True),
            "MSFT": UniverseAsset("MSFT", "NASDAQ", "Software", 3200.0, True),
            "TSLA": UniverseAsset("TSLA", "NASDAQ", "Automotive", 800.0, False) # Inactive/Excluded asset
        }

    def is_eligible(self, symbol: str) -> bool:
        asset = self._registry.get(symbol)
        return asset is not None and asset.is_active

    def get_asset(self, symbol: str) -> UniverseAsset:
        return self._registry.get(symbol)
