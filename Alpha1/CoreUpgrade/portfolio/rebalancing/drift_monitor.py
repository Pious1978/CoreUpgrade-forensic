from typing import Dict, Any

class DriftMonitor:
    """
    Monitors portfolio weight drift and risk parameter deviations to trigger rebalancing cycles.
    """
    
    def __init__(self, target_weights: Dict[str, float], weight_tolerance: float = 0.02):
        self.target_weights = target_weights
        self.tolerance = weight_tolerance

    def check_drift(self, current_weights: Dict[str, float]) -> Dict[str, Any]:
        drifted_assets = []
        max_drift = 0.0
        
        all_symbols = set(self.target_weights.keys()).union(set(current_weights.keys()))
        for sym in all_symbols:
            t_w = self.target_weights.get(sym, 0.0)
            c_w = current_weights.get(sym, 0.0)
            diff = abs(c_w - t_w)
            max_drift = max(max_drift, diff)
            if diff > self.tolerance:
                drifted_assets.append({"symbol": sym, "target": t_w, "current": c_w, "drift": round(diff, 4)})

        needs_rebalance = len(drifted_assets) > 0 or max_drift > self.tolerance
        return {
            "needs_rebalance": needs_rebalance,
            "max_drift": round(max_drift, 4),
            "drifted_assets": drifted_assets
        }
