# portfolio/optimization/certification/theorem_optimizer_replay_001.py
from portfolio.optimization.contracts.optimization_contract import OptimizationResult

class OptimizerReplayTheorem:
    """
    THEOREM-OPTIMIZER-REPLAY-001
    Invariant: Identical optimization inputs + identical solver environment 
    must produce an identical OptimizationResult fingerprint.
    """
    id = "THEOREM-OPTIMIZER-REPLAY-001"
    version = "1.0.0"

    @classmethod
    def verify(
        cls,
        original_result: OptimizationResult,
        replay_result: OptimizationResult
    ) -> dict:
        
        identical = (original_result.result_hash == replay_result.result_hash)

        if not identical:
            return {
                "certified": False,
                "reason": "Optimizer replay divergence detected. Result fingerprint mismatch.",
                "original_hash": original_result.result_hash,
                "replay_hash": replay_result.result_hash
            }

        return {
            "certified": True,
            "original_hash": original_result.result_hash,
            "replay_hash": replay_result.result_hash,
            "reason": None
        }
