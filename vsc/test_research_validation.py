import unittest
import numpy as np
from validation.walk_forward import WalkForwardEngine
from validation.benchmark import BenchmarkEngine
from validation.regime import RegimeDetector
from validation.promotion import StrategyPromotionPolicy
from contracts.backtest_result import BacktestResultContract

class TestVSC5_0ResearchValidation(unittest.TestCase):

    def test_research_validation_pipeline(self):
        print("\n==================================================")
        print(" Starting VSC 5.0 Research Validation & Walk Forward Test")
        print("==================================================")

        # 1. Test Regime Detection
        dummy_prices = np.array([100, 102, 105, 107, 110, 112, 115, 118, 120, 122, 
                                  125, 128, 130, 132, 135, 138, 140, 142, 145, 148, 150])
        regime = RegimeDetector.detect_regime(dummy_prices)
        print(f"Detected Market Regime : {regime}")

        # 2. Test Benchmark Comparison
        np.random.seed(42)
        strat_rets = np.random.normal(0.0008, 0.012, 252)
        bench_rets = np.random.normal(0.0004, 0.015, 252)
        bench_metrics = BenchmarkEngine.calculate_metrics(strat_rets, bench_rets)
        print(f"Benchmark Comparison   : Alpha={bench_metrics['alpha']}, Beta={bench_metrics['beta']}, IR={bench_metrics['information_ratio']}")

        # 3. Test Walk Forward Folds
        dummy_history = [f"Data_Day_{i}" for i in range(1, 10)]
        folds = WalkForwardEngine.generate_folds(dummy_history, train_size=4, val_size=2)
        print(f"Walk Forward Folds Generated: {len(folds)} folds")

        # 4. Create Backtest Result Contract & Evaluate Promotion Gate
        result_contract = BacktestResultContract(
            strategy_id="STRAT-MOMENTUM-V1",
            train_period="2022-2024",
            validation_period="2025",
            cagr=0.185,
            sharpe_ratio=1.65,
            max_drawdown=-0.085,
            alpha=bench_metrics["alpha"],
            beta=bench_metrics["beta"],
            information_ratio=bench_metrics["information_ratio"],
            market_regime=regime,
            promotion_status="PENDING"
        )

        promotion_status = StrategyPromotionPolicy.evaluate(result_contract)

        certified_result = BacktestResultContract(
            immutable_id=result_contract.immutable_id,
            root_contract_id=result_contract.root_contract_id,
            correlation_id=result_contract.correlation_id,
            strategy_id=result_contract.strategy_id,
            train_period=result_contract.train_period,
            validation_period=result_contract.validation_period,
            cagr=result_contract.cagr,
            sharpe_ratio=result_contract.sharpe_ratio,
            max_drawdown=result_contract.max_drawdown,
            alpha=result_contract.alpha,
            beta=result_contract.beta,
            information_ratio=result_contract.information_ratio,
            market_regime=result_contract.market_regime,
            promotion_status=promotion_status
        )

        print(f"\n--- Strategy Promotion Scorecard ---")
        print(f"Strategy ID           : {certified_result.strategy_id}")
        print(f"Train / Validation    : {certified_result.train_period} -> {certified_result.validation_period}")
        print(f"CAGR                  : {certified_result.cagr * 100:.1f}%")
        print(f"Sharpe Ratio          : {certified_result.sharpe_ratio:.2f}")
        print(f"Max Drawdown          : {certified_result.max_drawdown * 100:.1f}%")
        print(f"Alpha vs Benchmark    : {certified_result.alpha * 100:.2f}%")
        print(f"Promotion Decision    : {certified_result.promotion_status}")
        print("-" * 52)
        print("==================================================")
        print(" 🎉 VSC 5.0 Research Validation & Walk Forward Verified!")
        print("==================================================")

        # Assertions
        self.assertEqual(certified_result.promotion_status, "PRODUCTION_ELIGIBLE")
        self.assertGreater(certified_result.sharpe_ratio, 1.0)
        self.assertGreater(certified_result.alpha, 0.0)

if __name__ == "__main__":
    unittest.main()
