from contracts.strategy_validation import StrategyValidationContract

class AdversarialValidator:
    """Inspects strategy definitions against strict institutional adversarial hurdles."""

    @staticmethod
    def validate_strategy(strategy_def: dict) -> StrategyValidationContract:
        strategy_id = strategy_def.get("strategy_id", "UNKNOWN")
        features = strategy_def.get("features", [])
        universe_type = strategy_def.get("universe_type", "FULL_HISTORICAL")
        params_tested_count = strategy_def.get("params_tested_count", 1)
        avg_daily_volume = strategy_def.get("avg_daily_volume", 1000000.0)
        walk_forward_passed = strategy_def.get("walk_forward_passed", True)

        checks = {
            "data_leakage": "PASS",
            "universe_integrity": "PASS",
            "liquidity": "PASS",
            "parameter_stability": "PASS",
            "walk_forward": "PASS"
        }
        failures = []

        # 1. Data Leakage / Future Information Check
        for feat in features:
            if any(term in feat.lower() for term in ["future", "tomorrow", "lookahead", "target"]):
                checks["data_leakage"] = "FAILED"
                failures.append("FUTURE_INFORMATION_DEPENDENCY")

        # 2. Universe Integrity Check
        if universe_type == "CURRENT_MEMBERS_ONLY":
            checks["universe_integrity"] = "FAILED"
            failures.append("SURVIVORSHIP_BIAS")

        # 3. Parameter Stability / Overfitting Check
        if params_tested_count > 100:
            checks["parameter_stability"] = "FAILED"
            failures.append("PARAMETER_DATA_MINING")

        # 4. Liquidity Check
        if avg_daily_volume < 500000.0:
            checks["liquidity"] = "FAILED"
            failures.append("LIQUIDITY_FAILURE")

        # 5. Walk Forward Check
        if not walk_forward_passed:
            checks["walk_forward"] = "FAILED"
            failures.append("WALK_FORWARD_FAILURE")

        status = "APPROVED" if len(failures) == 0 else "REJECTED"
        score = 1.0 if status == "APPROVED" else 0.0

        return StrategyValidationContract(
            strategy_id=strategy_id,
            status=status,
            validation_score=score,
            failures=tuple(failures)
        )
