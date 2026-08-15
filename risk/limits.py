class RiskLimits:
    MAX_POSITION_WEIGHT = 0.50
    MAX_PORTFOLIO_VOL = 0.25
    MAX_DRAWDOWN = 0.20
    MAX_CONCENTRATION = 0.50

    @classmethod
    def check_limits(cls, volatility: float, drawdown: float, concentration: float) -> bool:
        return (
            volatility <= cls.MAX_PORTFOLIO_VOL and
            drawdown <= cls.MAX_DRAWDOWN and
            concentration <= cls.MAX_CONCENTRATION
        )
