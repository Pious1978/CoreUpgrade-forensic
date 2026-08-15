from typing import Dict, Any, Callable, List

class IterativeOptimizationLoop:
    """
    Institutional convergence loop. Iterates between optimization, constraint validation,
    risk checking, and execution cost adjustment until portfolio state stabilizes.
    """
    
    def __init__(self, max_iterations: int = 5, weight_tolerance: float = 0.005):
        self.max_iterations = max_iterations
        self.tolerance = weight_tolerance

    def run_loop(
        self, 
        initial_weights: Dict[str, float], 
        optimizer_fn: Callable[[Dict[str, float]], Dict[str, float]], 
        constraint_fn: Callable[[Dict[str, float]], Dict[str, Any]], 
        risk_fn: Callable[[Dict[str, float]], Dict[str, Any]], 
        cost_fn: Callable[[Dict[str, float]], Dict[str, Any]]
    ) -> Dict[str, Any]:
        
        current_weights = initial_weights.copy()
        iteration = 0
        converged = False
        audit_trail: List[Dict[str, Any]] = []

        while iteration < self.max_iterations and not converged:
            iteration += 1
            
            # 1. Run Optimizer pass
            opt_weights = optimizer_fn(current_weights)
            
            # 2. Check Constraints & Auto-Repair Violations
            constraint_report = constraint_fn(opt_weights)
            if not constraint_report.get("passed", True):
                # Apply automated repair suggestions if available
                for violation in constraint_report.get("violations", []):
                    if violation.get("auto_fix_possible", False):
                        sym = violation["symbol"]
                        target_cap = violation["limit"]
                        opt_weights[sym] = target_cap

            # 3. Factor & Risk Check
            risk_report = risk_fn(opt_weights)
            
            # 4. Execution Cost Feedback Adjustment
            cost_report = cost_fn(opt_weights)
            
            audit_trail.append({
                "iteration": iteration,
                "weights": opt_weights,
                "constraints_passed": constraint_report.get("passed"),
                "risk_metrics": risk_report,
                "estimated_costs": cost_report
            })

            # Check convergence delta against previous weights
            max_delta = max(
                abs(opt_weights.get(k, 0.0) - current_weights.get(k, 0.0)) 
                for k in set(opt_weights).union(set(current_weights))
            )

            if max_delta < self.tolerance and constraint_report.get("passed", True):
                converged = True
            
            current_weights = opt_weights

        return {
            "converged": converged,
            "total_iterations": iteration,
            "final_weights": current_weights,
            "audit_trail": audit_trail
        }
