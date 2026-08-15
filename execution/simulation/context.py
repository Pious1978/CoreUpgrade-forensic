from dataclasses import dataclass
from decimal import Decimal
from functools import cached_property
from typing import ClassVar, NewType
import hashlib
import json
from execution.contracts.market_snapshot_contract import MarketSnapshotContract
from execution.simulation.metadata import ExecutionModelMetadata

SimulationFingerprint = NewType(
    "SimulationFingerprint",
    str,
)

@dataclass(frozen=True, slots=True)
class ExecutionSimulationContext:
    SCHEMA_VERSION: ClassVar[str] = "1.1"

    market_snapshot: MarketSnapshotContract
    liquidity_score: Decimal
    volatility: Decimal
    deterministic_seed: int
    metadata: ExecutionModelMetadata

    @cached_property
    def fingerprint(self) -> SimulationFingerprint:
        data = {
            "schema_version": self.SCHEMA_VERSION,
            "market_snapshot_hash": str(
                self.market_snapshot.fingerprint()
            ),
            "liquidity_score": str(self.liquidity_score),
            "volatility": str(self.volatility),
            "deterministic_seed": self.deterministic_seed,
            "metadata": self.metadata.to_dict(),
        }

        canonical = json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
        )

        return SimulationFingerprint(
            hashlib.sha256(
                canonical.encode("utf-8")
            ).hexdigest()
        )
