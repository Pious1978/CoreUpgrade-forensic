class GranularConstraintEngine:
    """
    Institutional constraint engine returning actionable violation objects with repair costs and auto-fix metadata.
    """
    
    def __init__(self, limits: Dict[str, Any] = None):
        self.limits = limits or {"max_position_weight": 0.25, "min_cash_floor": 0.05}

    def validate_constraints(self, weights: Dict[str, float], cash_pct: float) -> Dict[str, Any]:
        violations = []
        
        if cash_pct < self.limits["min_cash_floor"]:
            violations.append({
                "category": "CASH_FLOOR",
                "severity": "HIGH",
                "description": f"Cash {cash_pct*100:.1f}% below floor {self.limits['min_cash_floor']*100}%",
                "repair_suggestion": "Scale down pro-rata buy orders",
                "auto_fix_possible": True
            })

        for sym, w in weights.items():
            if w > self.limits["max_position_weight"]:
                violations.append({
                    "category": "POSITION_WEIGHT",
                    "severity": "CRITICAL",
                    "symbol": sym,
                    "limit": self.limits["max_position_weight"],
                    "current": w,
                    "description": f"Asset {sym} weight {w*100:.1f}% exceeds cap",
                    "repair_suggestion": f"Capped weight to {self.limits['max_position_weight']*100}%",
                    "auto_fix_possible": True
                })

        return {
            "passed": len(violations) == 0,
            "violations": violations
        }
