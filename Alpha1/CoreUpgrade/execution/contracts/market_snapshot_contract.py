from uuid import UUID
from decimal import Decimal
from dataclasses import dataclass
import hashlib
import json

MARKET_SNAPSHOT_SCHEMA_VERSION = "1.0"

@dataclass(frozen=True, slots=True)
class MarketSnapshotContract:
    snapshot_id: UUID
    symbol: str
    bid: Decimal
    ask: Decimal
    last_price: Decimal
    volume: Decimal
    timestamp: int

    def fingerprint(self) -> str:
        data = {
            "schema_version": MARKET_SNAPSHOT_SCHEMA_VERSION,
            "snapshot_id": str(self.snapshot_id),
            "symbol": self.symbol,
            "bid": str(self.bid),
            "ask": str(self.ask),
            "last_price": str(self.last_price),
            "volume": str(self.volume),
            "timestamp": self.timestamp,
        }
        canonical = json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
