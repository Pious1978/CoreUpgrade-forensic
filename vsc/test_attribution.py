import unittest
import numpy as np
from simulation.simulator import ClosedLoopSimulator
from execution.planner import ExecutionIntelligenceEngine
from contracts.portfolio_risk import PortfolioRiskContract
from attribution.engine import PerformanceAttributionEngine

class TestVSC4_9PerformanceAttribution(unittest.TestCase):

    def test_attribution_and_learning_loop(self):
        print("\n==================================================")
        print(" Starting VSC 4.9 Performance Attribution Test")
        print("==================================================")

        # 1. Run Closed-Loop Simulation
        sim = ClosedLoopSimulator(initial_capital=1000000.0)
        
        market_data_t1 = {
            "prices": {"NVDA": 900.0, "MSFT": 350.0},
            "returns": np.random.normal(0.0005, 0.015, 252)
        }
        orders_t1 = {
            "NVDA": {"side": "BUY", "quantity": 100.0, "price": 900.0},
            "MSFT": {"side": "BUY", "quantity": 300.0, "price": 350.0}
        }
        sim.step(orders_t1, market_data_t1)

        market_data_t2 = {
            "prices": {"NVDA": 950.0, "MSFT": 360.0},
            "returns": np.random.normal(0.0005, 0.015, 252)
        }
        orders_t2 = {
            "NVDA": {"side": "SELL", "quantity": 50.0, "price": 950.0}
        }
        sim.step(orders_t2, market_data_t2)

        # 2. Generate Execution Decisions for Quality Grading
        risk_contract = PortfolioRiskContract(
            portfolio_id="PORTFOLIO-ALPHA-01",
            portfolio_value=sim.current_snapshot.total_portfolio_value,
            volatility=0.14,
            risk_status="APPROVED"
        )
        exec_engine = ExecutionIntelligenceEngine()
        decisions = exec_engine.plan_execution(risk_contract, orders_t2)

        # 3. Evaluate Attribution & Learning Feedback
        attr_engine = PerformanceAttributionEngine()
        attribution = attr_engine.evaluate(sim.snapshot_history, sim.ledger_history, execution_decisions=decisions)

        print("\n--- Performance Attribution & Alpha Decomposition ---")
        print(f"Portfolio ID             : {attribution.portfolio_id}")
        print(f"Initial Capital          : ₹{attribution.initial_capital:,.2f}")
        print(f"Final Portfolio Value    : ₹{attribution.final_portfolio_value:,.2f}")
        print(f"Cumulative Return        : {attribution.cumulative_return_pct:.2f}%")
        print(f"Sharpe Ratio             : {attribution.sharpe_ratio:.2f}")
        
        print(f"\nAsset Attribution Breakdown:")
        for sym, metrics in attribution.attribution_breakdown.items():
            print(f"  [{sym}] PnL: ₹{metrics['unrealized_pnl']:,.2f} | Alpha: ₹{metrics['research_alpha']:,.2f} | Beta: ₹{metrics['market_beta']:,.2f} | Weight: {metrics['weight']*100:.1f}%")

        print(f"\nExecution Quality Report:")
        for sym, eq in attribution.execution_quality_report.items():
            print(f"  [{sym}] Strategy: {eq.get('strategy_used', 'N/A')} | Rating: {eq['realized_rating']}")

        print(f"\nSignal Learning Feedback Loop:")
        feedback = attribution.signal_learning_feedback
        print(f"  Historical Signals Evaluated : {feedback['historical_signals_evaluated']}")
        print(f"  Win Rate                     : {feedback['win_rate_pct']}%")
        print(f"  Confidence Adjustment Factor : +{feedback['confidence_adjustment_factor']}")
        print(f"  Learning Status              : {feedback['learning_status']}")
        print("-" * 52)
        print("==================================================")
        print(" 🎉 VSC 4.9 Performance Attribution & Learning Verified!")
        print("==================================================")

        # Invariant Assertions
        self.assertEqual(attribution.portfolio_id, "PORTFOLIO-ALPHA-01")
        self.assertGreater(attribution.final_portfolio_value, 0.0)
        self.assertIn("NVDA", attribution.attribution_breakdown)
        self.assertIn("MSFT", attribution.attribution_breakdown)
        self.assertIn("confidence_adjustment_factor", attribution.signal_learning_feedback)

if __name__ == "__main__":
    unittest.main()
