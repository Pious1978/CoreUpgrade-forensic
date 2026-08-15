from typing import Dict, Any, List

class AuditStatistics:
    """Aggregates and computes historical execution analytics across audit runs."""

    @staticmethod
    def compute_historical_analytics(run_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not run_history:
            return {"total_runs": 0, "average_score": 0.0}

        total_runs = len(run_history)
        scores = [run.get("final_score", 0.0) for run in run_history]
        avg_score = sum(scores) / total_runs

        return {
            "total_runs": total_runs,
            "average_score": round(avg_score, 2),
            "min_score": min(scores),
            "max_score": max(scores)
        }
