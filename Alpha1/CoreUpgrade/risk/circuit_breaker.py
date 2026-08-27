from risk.limits import RiskLimits

class PortfolioCircuitBreaker:
    """Evaluates risk metrics against mandate limits to approve or reject portfolio execution."""

    def evaluate(self, risk_contract) -> bool:
        return RiskLimits.check_limits(
            volatility=risk_contract.volatility,
            drawdown=risk_contract.max_drawdown,
            concentration=risk_contract.concentration_score
        )
