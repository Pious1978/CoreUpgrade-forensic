# portfolio/universe/universe_definition.py
import dataclasses
from typing import Tuple
from portfolio.universe.eligibility_rules import UniverseFilter
from research.governance.serialization import CanonicalSerializer

@dataclasses.dataclass(frozen=True)
class UniverseDefinition:
    definition_id: str
    base_population: str  # e.g., "NSE_ALL_EQUITIES"
    filters: Tuple[UniverseFilter, ...]
    
    @property
    def ruleset_hash(self) -> str:
        # Cryptographically binds the definition to the exact filter parameters
        payload = {
            "definition": self.definition_id,
            "base": self.base_population,
            "filters": tuple((f.filter_id, f.parameters) for f in self.filters)
        }
        return CanonicalSerializer.hash(payload)
