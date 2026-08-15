from dataclasses import dataclass


@dataclass(frozen=True)
class RiskConstraints:
    max_position_size: float
    max_sector_exposure: float
    max_drawdown: float
    volatility_target: float
