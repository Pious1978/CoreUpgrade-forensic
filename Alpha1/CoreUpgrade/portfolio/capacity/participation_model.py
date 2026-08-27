from typing import Dict, Any

class ParticipationModel:
    """Evaluates whether an order size violates institutional ADV participation limits."""
    
    def evaluate_participation(self, order_shares: float, adv_shares: float, participation_limit: float = 0.10) -> Dict[str, Any]:
        if adv_shares <= 0:
            return {"status": "IMPOSSIBLE", "participation_rate": 1.0}

        rate = order_shares / adv_shares
        status = "SAFE" if rate <= participation_limit else ("BORDERLINE" if rate <= (participation_limit * 2) else "IMPOSSIBLE")

        return {
            "participation_rate": round(rate * 100, 2),
            "status": status,
            "limit_violated": rate > participation_limit
        }
