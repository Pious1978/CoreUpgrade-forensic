import pandas as pd
from typing import Dict, Any, List
from validation.statistics import PerformanceStatistics
from validation.monte_carlo import MonteCarloEngine
from validation.walk_forward import WalkForwardEngine
from validation.scoring import InstitutionalScoringEngine

class ValidationReportGenerator:
    """
    Synthesizes audit metrics, eligibility gates, robustness, and execution assumptions.
    """
    
    def __init__(self, equity_curve: pd.Series, trades: List[Dict[str, Any]], exposure_metrics: Dict[str, Any] = None, lineage: Dict[str, str] = None, execution_assumptions: Dict[str, Any] = None):
        self.equity_curve = equity_curve
        self.trades = trades
        self.exposure_metrics = exposure_metrics or {"capital_exposure": {"max": 85.0}, "portfolio_heat": {"max": 3.1}}
        self.lineage = lineage or {"experiment_id": "EXP_20260731_001", "strategy_version": "VCP_ENGINE_v15"}
        self.execution_assumptions = execution_assumptions or {
            "brokerage": 0.03,
            "slippage": 0.15,
            "impact_model": "MEDIUM_VOLUME",
            "entry_rule": "NEXT_DAY_OPEN",
            "exit_rule": "TRAILING_STOP"
        }

    def generate_audit_report(self) -> Dict[str, Any]:
        stats = PerformanceStatistics(self.equity_curve, self.trades)
        perf_metrics = stats.compute_all()
        
        mc = MonteCarloEngine(self.trades)
        mc_results = mc.run_simulation()
        
        wf = WalkForwardEngine(pd.DataFrame({'portfolio_value': self.equity_curve}))
        wf_results = wf.run_walk_forward()
        
        scoring_engine = InstitutionalScoringEngine(
            wf_results=wf_results,
            mc_results=mc_results,
            risk_metrics=perf_metrics["risk_metrics"],
            trade_metrics=perf_metrics["trading_metrics"]
        )
        scoring_output = scoring_engine.compute_score()
        
        return {
            "institutional_audit_status": "APPROVED" if scoring_output["eligibility"]["approved"] else "REJECTED",
            "credibility_score": scoring_output["score"],
            "eligibility_gates": scoring_output["eligibility"],
            "data_lineage": self.lineage,
            "execution_assumptions": self.execution_assumptions,
            "score_breakdown": scoring_output["score_breakdown"],
            "performance_summary": perf_metrics,
            "exposure_summary": self.exposure_metrics,
            "monte_carlo_distribution": mc_results,
            "walk_forward_validation": wf_results
        }
