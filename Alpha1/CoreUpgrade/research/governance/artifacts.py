# research/governance/artifacts.py
import dataclasses
from typing import Tuple

@dataclasses.dataclass(frozen=True)
class TheoremIdentity:
    id: str
    version: str
    implementation_hash: str

@dataclasses.dataclass(frozen=True)
class GovernanceManifest:
    engine_version: str = "1.0.0-frozen"
    schema_version: str = "v2.1"
    active_theorems: Tuple[TheoremIdentity, ...]

@dataclasses.dataclass(frozen=True)
class CertificationFingerprint:
    algorithm: str
    manifest_hash: str
    dag_hash: str
    proof_hash: str
    certification_hash: str
    overall_hash: str
