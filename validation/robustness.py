from typing import Dict, Any, List, Callable

class RobustnessEngine:
    """
    Multi-dimensional robustness testing covering parameters, transaction costs, and asset universes.
    """
    
    def __init__(self, strategy_runner: Callable[[Dict[str, Any]], Dict[str, Any]], baseline_cagr: float):
        self.strategy_runner = strategy_runner
        self.baseline_cagr = baseline_cagr

    def run_parameter_sensitivity(self, parameter_grid: List[Dict[str, Any]]) -> Dict[str, Any]:
        cagrs = []
        for params in parameter_grid:
            metrics = self.strategy_runner(params)
            cagrs.append(metrics.get("cagr", 0))
            
        median_cagr = sorted(cagrs)[len(cagrs) // 2] if cagrs else 0.0
        score = round(min(100.0, max(0.0, (median_cagr / max(self.baseline_cagr, 1e-4)) * 100.0)), 2)
        return {"test_type": "parameter_sensitivity", "robustness_score": score, "median_cagr": median_cagr}

    def run_cost_sensitivity(self, cost_grid: List[float], base_metrics_fn: Callable[[float], Dict[str, Any]]) -> Dict[str, Any]:
        results = []
        for cost in cost_grid:
            metrics = base_metrics_fn(cost)
            cagr = metrics.get("cagr", 0)
            results.append({"cost_bps": cost * 10000, "cagr": cagr})
            
        survival = round(min(100.0, max(0.0, (results[-1]["cagr"] / max(self.baseline_cagr, 1e-4)) * 100.0)), 2)
        return {"test_type": "cost_sensitivity", "cost_survival_score": survival, "results": results}

    def run_universe_robustness(self, universe_grid: Dict[str, Callable[[], Dict[str, Any]]]) -> Dict[str, Any]:
        results = {}
        for universe_name, runner in universe_grid.items():
            metrics = runner()
            results[universe_name] = {
                "cagr": metrics.get("cagr", 0),
                "sharpe": metrics.get("sharpe", 0)
            }
        return {"test_type": "universe_robustness", "universes_tested": list(universe_grid.keys()), "results": results}
