from typing import Dict, Any, List

class PolicyEngine:
    """
    Evaluates portfolio weight matrices and risk metrics against dynamic institutional policies.
    """
    
    def __init__(self, policy_config: Dict[str, Any] = None):
        self.config = policy_config or {
            "max_position_weight": 0.25,
            "max_sector_weight": 0.40,
            "min_cash_floor": 0.05,
            "max_portfolio_beta": 1.15,
            "max_daily_turnover": 0.30
        }

    def evaluate_policies(self, weights: Dict[str, float], cash_pct: float, portfolio_beta: float) -> List[Dict[str, Any]]:
        violations = []

        if cash_pct < self.config["min_cash_floor"]:
            violations.append({
                "policy": "CASH_FLOOR",
                "severity": "HIGH",
                "message": f"Cash {cash_pct*100:.1f}% violates minimum floor {self.config['min_cash_floor']*100}%"
            })

        if portfolio_beta > self.config["max_portfolio_beta"]:
            violations.append({
                "policy": "PORTFOLIO_BETA",
                "severity": "CRITICAL",
                "message": f"Portfolio beta {portfolio_beta:.2f} exceeds cap {self.config['max_portfolio_beta']}"
            })

        for sym, w in weights.items():
            if w > self.config["max_position_weight"]:
                violations.append({
                    "policy": "POSITION_CONCENTRATION",
                    "severity": "CRITICAL",
                    "symbol": sym,
                    "message": f"Asset {sym} weight {w*100:.1f}% exceeds max limit {self.config['max_position_weight']*100}%"
                })

        return violations
