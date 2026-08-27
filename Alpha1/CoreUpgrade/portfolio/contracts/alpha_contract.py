# portfolio/contracts/alpha_contract.py
import dataclasses
from datetime import datetime
from decimal import Decimal
from typing import Tuple
from portfolio.contracts.asset_contract import AssetIdentity
from research.governance.serialization import CanonicalSerializer

@dataclasses.dataclass(frozen=True)
class ResearchCertificationReference:
    """Cryptographic proof that the alpha generator passed governance."""
    fingerprint: str
    certification_status: str
    failed_theorems: Tuple[str, ...]
    manifest_hash: str

@dataclasses.dataclass(frozen=True)
class CertifiedAlpha:
    instrument_id: str
    expected_return: Decimal
    confidence_score: Decimal
    horizon_days: int

@dataclasses.dataclass(frozen=True)
class CertifiedAlphaVector:
    vector_id: str
    certification: ResearchCertificationReference
    timestamp: datetime
    alphas: Tuple[CertifiedAlpha, ...]
