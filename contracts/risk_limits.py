from dataclasses import dataclass

@dataclass(frozen=True)
class RiskLimitContract:
    """Public boundary contract between Risk/Governance and Portfolio."""
    max_position_size: float
    max_sector_exposure: float
    max_drawdown_limit: float
