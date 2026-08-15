# portfolio/contracts/universe_contract.py
import dataclasses
from datetime import datetime
from typing import Tuple
from portfolio.contracts.asset_contract import AssetIdentity
from research.governance.serialization import CanonicalSerializer

@dataclasses.dataclass(frozen=True)
class UniverseDefinition:
    definition_id: str
    base_population_id: str
    filters: Tuple['FilterIdentity', ...]
    
    @property
    def ruleset_hash(self) -> str:
        return CanonicalSerializer.hash(self)

@dataclasses.dataclass(frozen=True)
class UniverseCertificate:
    universe_id: str
    timestamp: datetime
    assets: Tuple[AssetIdentity, ...]
    ruleset_hash: str
    metadata_snapshot_hash: str
    
    @property
    def certificate_hash(self) -> str:
        return CanonicalSerializer.hash(self)

@dataclasses.dataclass(frozen=True)
class UniverseDelta:
    """Audit trail representing index/universe reconstitutions."""
    previous_hash: str
    current_hash: str
    timestamp: datetime
    added: Tuple[AssetIdentity, ...]
    removed: Tuple[AssetIdentity, ...]
