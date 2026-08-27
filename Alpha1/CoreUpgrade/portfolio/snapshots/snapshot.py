import json
from typing import Dict, Any

class PortfolioSnapshot:
    """
    Creates point-in-time snapshots of portfolio state for auditing, debugging, 
    and multi-dimensional performance attribution.
    """
    
    def __init__(self, timestamp: str, nav: float, cash: float, weights: Dict[str, float], positions: Dict[str, Any]):
        self.snapshot = {
            "timestamp": timestamp,
            "nav": round(nav, 2),
            "cash": round(cash, 2),
            "weights": {k: round(v, 4) for k, v in weights.items()},
            "positions": positions
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.snapshot

    def to_json(self) -> str:
        return json.dumps(self.snapshot, indent=2)
