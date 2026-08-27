from typing import Dict, Any

class InstitutionalScoringEngine:
    """
    Separates quantitative scoring from hard institutional risk eligibility gates.
    """
    
    def __init__(self, wf_results: Dict[str, Any], mc_results: Dict[str, Any], risk_metrics: Dict[str, Any], trade_metrics: Dict[str, Any]):
        self.wf = wf_results
        self.mc = mc_results
        self.risk = risk_metrics
        self.trades = trade_metrics

    def compute_score(self) -> Dict[str, Any]:
        stability = self.wf.get("stability_score", 0.0)
        wf_score = round((stability / 100.0) * 30.0, 1)

        cagr_5th = self.mc.get("cagr_percentiles", {}).get("5th", -10.0)
        mc_score = 25.0 if cagr_5th > 0 else max(0.0, 25.0 + (cagr_5th / 10.0) * 25.0)
        mc_score = round(min(25.0, max(0.0, mc_score)), 1)

        sharpe = self.risk.get("sharpe", 0.0)
        risk_score = round(min(20.0, max(0.0, (sharpe / 2.0) * 20.0)), 1)

        max_dd = abs(self.risk.get("max_drawdown", 50.0))
        dd_score = round(max(0.0, 15.0 - (max_dd / 25.0) * 15.0), 1)

        pf = self.trades.get("profit_factor", 1.0)
        t_score = round(min(10.0, max(0.0, (pf / 2.0) * 10.0)), 1)

        base_total = wf_score + mc_score + risk_score + dd_score + t_score

        # Hard Eligibility Evaluation
        approved = True
        reasons = []

        if max_dd > 40.0:
            approved = False
            reasons.append("Max drawdown exceeds 40% threshold limit.")
        if sharpe < 0.5:
            approved = False
            reasons.append("Sharpe ratio below 0.5 minimum institutional requirement.")
        if self.wf.get("stability_score", 0) < 50.0:
            approved = False
            reasons.append("Walk-forward stability score below 50%.")

        penalty = 1.0
        if max_dd > 30.0:
            penalty *= 0.7
        if sharpe < 0.8:
            penalty *= 0.85

        final_total = round(base_total * penalty, 1)

        return {
            "score": final_total,
            "eligibility": {
                "approved": approved,
                "reasons": reasons if reasons else ["All hard risk gates passed successfully."]
            },
            "score_breakdown": {
                "walk_forward": wf_score,
                "monte_carlo": mc_score,
                "risk": risk_score,
                "drawdown": dd_score,
                "trade_quality": t_score
            }
        }
