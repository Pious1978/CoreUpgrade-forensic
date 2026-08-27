# research/governance/manifest.py
import dataclasses
from typing import Tuple
from research.governance.serialization import CanonicalSerializer

@dataclasses.dataclass(frozen=True)
class GovernanceManifest:
    engine_version: str = "1.0.0-frozen"
    schema_version: str = "v2.1"
    # Now explicitly locks the algebra implementation version
    active_theorems: Tuple[str, ...] = (
        "THEOREM-TEMPORAL-001@1.2.0", 
        "THEOREM-PERFORMANCE-001@1.0.0"
    )
    
    @property
    def identity_hash(self) -> str:
        return CanonicalSerializer.fingerprint(self)
