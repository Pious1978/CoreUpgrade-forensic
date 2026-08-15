class ModelDriftAuditor:
    """Detects performance degradation and model drift between expected backtest metrics and live telemetry."""

    MAX_SHARPE_DECAY_PCT = 0.40  # Trigger review if Sharpe drops by > 40%

    @classmethod
    def audit_drift(cls, registry_contract, live_sharpe_ratio: float) -> dict:
        expected_sharpe = registry_contract.sharpe_ratio
        if expected_sharpe <= 0:
            return {"status": "NORMAL", "drift_detected": False}

        decay = (expected_sharpe - live_sharpe_ratio) / expected_sharpe
        
        if decay > cls.MAX_SHARPE_DECAY_PCT:
            return {
                "status": "STRATEGY_REVIEW_REQUIRED",
                "drift_detected": True,
                "expected_sharpe": expected_sharpe,
                "live_sharpe": live_sharpe_ratio,
                "decay_pct": round(decay * 100, 2)
            }
        
        return {
            "status": "NORMAL",
            "drift_detected": False,
            "decay_pct": round(decay * 100, 2)
        }
