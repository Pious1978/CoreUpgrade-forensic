import os

gate2_code = '''import hashlib
from datetime import datetime
from typing import Dict, Any, List
from contracts.signal_validation import SignalValidationResult

class ResearchValidityGate:
    """
    Gate 2: Institutional Research Validity
    Evaluates backtest artifacts and issues a Capital Eligibility object (SignalValidationResult)
    required by the Portfolio Optimizer.
    """
    def __init__(self, min_oos_sharpe: float = 1.0, min_deflated_sharpe: float = 0.5):
        self.min_oos_sharpe = min_oos_sharpe
        self.min_deflated_sharpe = min_deflated_sharpe

    def evaluate_signal(self, candidate_id: str, backtest_data: Dict[str, Any]) -> SignalValidationResult:
        # 1. Look-Ahead Detection (Fatal if failed)
        look_ahead_pass = self._check_look_ahead(backtest_data)
        
        # 2. Out-of-Sample Performance
        oos_sharpe = backtest_data.get("oos_sharpe", 0.0)
        oos_pass = oos_sharpe >= self.min_oos_sharpe

        # 3. Walk-Forward Consistency
        wf_metrics = backtest_data.get("walk_forward_fold_returns", [])
        wf_pass = self._check_walk_forward(wf_metrics)

        # 4. TCA & Deflated Sharpe
        raw_sharpe = backtest_data.get("in_sample_sharpe", 0.0)
        est_turnover = backtest_data.get("annual_turnover", 0.0)
        deflated_sharpe = self._calculate_deflated_sharpe(raw_sharpe, est_turnover)
        tca_pass = deflated_sharpe >= self.min_deflated_sharpe

        # 5. Reproducibility Hash (Locks the parameters)
        rep_hash = self._generate_parameter_hash(backtest_data.get("parameters", {}))

        # Determine Capital Eligibility Verdict
        if not look_ahead_pass:
            verdict = "FAIL"
        elif oos_pass and wf_pass and tca_pass:
            verdict = "PASS"
        else:
            verdict = "CONDITIONAL"

        return SignalValidationResult(
            signal_id=f"{candidate_id}_{rep_hash[:8]}",
            verdict=verdict,
            oos_sharpe=oos_sharpe,
            deflated_sharpe=deflated_sharpe,
            p_value=backtest_data.get("p_value", 1.0),
            capacity_limit=backtest_data.get("capacity_limit_usd", 0.0),
            allowed_regimes=backtest_data.get("allowed_regimes", ["ALL"]),
            validation_timestamp=datetime.utcnow()
        )

    def _check_walk_forward(self, fold_returns: List[float]) -> bool:
        """Ensures consistency: >60% of folds must be positive."""
        if not fold_returns: return False
        positive_folds = sum(1 for r in fold_returns if r > 0)
        return (positive_folds / len(fold_returns)) >= 0.60

    def _check_look_ahead(self, data: Dict[str, Any]) -> bool:
        """Verifies no future data leakage exists in the pipeline design."""
        # A hard failure flag injected by earlier runtime data checkers
        return data.get("look_ahead_flag", False) == False

    def _calculate_deflated_sharpe(self, raw_sharpe: float, turnover: float) -> float:
        """Penalizes theoretical Sharpe based on estimated trading friction."""
        # Simple heuristic: subtract 0.1 Sharpe per 100% turnover
        penalty = turnover * 0.1
        return max(0.0, raw_sharpe - penalty)

    def _generate_parameter_hash(self, params: Dict[str, Any]) -> str:
        """Creates a deterministic fingerprint of the strategy parameters."""
        sorted_params = str(sorted(params.items()))
        return hashlib.sha256(sorted_params.encode()).hexdigest()

if __name__ == "__main__":
    # Test the Gate with a mock research signal
    gate = ResearchValidityGate()
    
    mock_signal = {
        "oos_sharpe": 1.2,
        "in_sample_sharpe": 1.8,
        "walk_forward_fold_returns": [0.05, 0.02, -0.01, 0.04, 0.03],
        "annual_turnover": 3.5, # 350% turnover
        "look_ahead_flag": False,
        "p_value": 0.02,
        "capacity_limit_usd": 50000000.0,
        "allowed_regimes": ["BULL", "HIGH_VOL"],
        "parameters": {"lookback": 20, "z_score_threshold": 2.0}
    }
    
    result = gate.evaluate_signal("MOMENTUM_STRAT_01", mock_signal)
    
    print(f"Gate 2 Execution Complete.\\nVerdict: {result.verdict}")
    print(f"Signal ID Hash: {result.signal_id}")
    print(f"Deflated Sharpe (post-TCA): {result.deflated_sharpe:.2f}")
'''

os.makedirs("audits", exist_ok=True)
with open(os.path.join("audits", "gate2_research_validity.py"), "w", encoding="utf-8") as f:
    f.write(gate2_code)

print("Created audits/gate2_research_validity.py")
