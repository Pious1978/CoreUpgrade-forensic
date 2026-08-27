from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

@dataclass(frozen=True, slots=True)
class CertifiedStrategyContract:
    """
    Immutable admission token issued by the certification engine, 
    permitting a certified strategy to interface with portfolio construction.
    """
    strategy_id: str
    certification_id: str
    certification_fingerprint: str
    validator_versions: tuple[str, ...]
    approved_timestamp: datetime
    max_capital_allocation: Decimal

    def __post_init__(self) -> None:
        if not self.strategy_id:
            raise ValueError("Strategy ID cannot be empty.")
        if not self.certification_id:
            raise ValueError("Certification ID cannot be empty.")
        if not self.certification_fingerprint:
            raise ValueError("Certification fingerprint cannot be empty.")
        if not self.validator_versions:
            raise ValueError("Validator versions tuple cannot be empty.")
        if self.max_capital_allocation < Decimal("0"):
            raise ValueError("Max capital allocation cannot be negative.")
