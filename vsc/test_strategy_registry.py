import unittest
from registry.manager import StrategyRegistry
from contracts.strategy_promotion import StrategyPromotionContract
from audits.drift_audit import ModelDriftAuditor

class TestVSC5_5StrategyRegistry(unittest.TestCase):

    def test_strategy_registry_and_audits(self):
        print("\n==================================================")
        print(" Starting VSC 5.5 Strategy Registry & Audit Test")
        print("==================================================")

        registry = StrategyRegistry()

        # 1. Generate Experiment Tracking ID
        params = {"lookback": 20, "threshold": 1.5, "stop_loss": 0.05}
        exp_id = StrategyRegistry.generate_experiment_id("STRAT-MOMENTUM-V1", params)
        print(f"Generated Experiment ID : {exp_id}")

        # 2. Create Strategy Promotion Contract
        promotion_contract = StrategyPromotionContract(
            strategy_id="STRAT-MOMENTUM-V1",
            version="1.0",
            experiment_id=exp_id,
            dataset_version="DS-US-EQUITY-2026-Q1",
            validation_period="2025",
            cagr=0.185,
            sharpe_ratio=1.65,
            max_drawdown=-0.085,
            alpha=0.1377,
            promotion_status="PRODUCTION_ELIGIBLE",
            approved_by_policy=True
        )

        # 3. Register Strategy
        registered = registry.register_strategy(promotion_contract)
        self.assertTrue(registered)
        print(f"Strategy Registration   : SUCCESS ({promotion_contract.strategy_id})")

        # 4. Test Model Drift Detection (Normal vs Degraded)
        stored_strategy = registry.get_strategy("STRAT-MOMENTUM-V1", "1.0")
        
        # Scenario A: Normal Performance
        drift_normal = ModelDriftAuditor.audit_drift(stored_strategy, live_sharpe_ratio=1.55)
        print(f"Drift Check (Normal)    : Status={drift_normal['status']}")

        # Scenario B: Significant Performance Decay (Triggers Review)
        drift_degraded = ModelDriftAuditor.audit_drift(stored_strategy, live_sharpe_ratio=0.85)
        print(f"Drift Check (Degraded)  : Status={drift_degraded['status']} (Decay: {drift_degraded['decay_pct']}%)")

        print("\n--- Strategy Registry Scorecard Summary ---")
        print(f"Registered Strategies   : {len(registry.registry)}")
        print(f"Audit Trail Entries     : {len(registry.experiment_audit_trail)}")
        print("-" * 52)
        print("==================================================")
        print(" 🎉 VSC 5.5 Strategy Registry & Governance Verified!")
        print("==================================================")

        # Invariant Assertions
        self.assertEqual(stored_strategy.experiment_id, exp_id)
        self.assertEqual(drift_normal["status"], "NORMAL")
        self.assertEqual(drift_degraded["status"], "STRATEGY_REVIEW_REQUIRED")

if __name__ == "__main__":
    unittest.main()
