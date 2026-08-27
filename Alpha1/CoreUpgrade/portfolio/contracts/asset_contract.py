# portfolio/contracts/asset_contract.py
import dataclasses

@dataclasses.dataclass(frozen=True)
class AssetIdentity:
    """Canonical namespace preventing symbol collision and ambiguity."""
    instrument_id: str  # Internal unique master identifier (e.g., "EQ-RELIANCE-IN")
    exchange: str       # "NSE", "BSE", "NYSE"
    isin: str           # "INE002A01018"
    asset_type: str     # "EQUITY", "ETF", "FUTURE"
