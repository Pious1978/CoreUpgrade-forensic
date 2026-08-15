class StrategyPromotionPolicy:
    """Evaluates backtest scorecards against institutional hurdles for production promotion."""
    
    MIN_SHARPE = 1.0
    MAX_DRAWDOWN = -0.20
    MIN_ALPHA = 0.01

    @classmethod
    def evaluate(cls, result) -> str:
        if (result.sharpe_ratio >= cls.MIN_SHARPE and 
            result.max_drawdown >= cls.MAX_DRAWDOWN and 
            result.alpha >= cls.MIN_ALPHA):
            return "PRODUCTION_ELIGIBLE"
        return "REJECTED_SUB_HURDLE"
