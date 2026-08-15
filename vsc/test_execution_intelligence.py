import unittest
from contracts.portfolio_risk import PortfolioRiskContract
from execution.planner import ExecutionIntelligenceEngine

class TestVSC4_5ExecutionIntelligence(unittest.TestCase):

    def test_execution_intelligence_pipeline(self):
        print("\n==================================================")
        print(" Starting VSC 4.5 Execution Intelligence Test")
        print("==================================================")

        # 1. Certified Risk Contract from VSC 4.0
        risk_contract = PortfolioRiskContract(
            portfolio_id="PORTFOLIO-ALPHA-01",
            portfolio_value=325050.0,
            volatility=0.1423,
            risk_status="APPROVED"
        )

        # 2. Target rebalancing orders
        target_orders = {
            "NVDA": {"side": "BUY", "quantity": 150.0, "price": 975.0},
            "MSFT": {"side": "BUY", "quantity": 380.0, "price": 385.0}
        }

        engine = ExecutionIntelligenceEngine()
        decisions = engine.plan_execution(risk_contract, target_orders)

        print("\n--- Execution Intelligence & Cost Analytics ---")
        for d in decisions:
            print(f"\nSymbol              : {d.symbol}")
            print(f"Side & Quantity     : {d.side} {d.quantity:,.1f} shares")
            print(f"Selected Strategy   : {d.selected_strategy}")
            print(f"Expected Spread Cost: ₹{d.expected_spread_cost:,.2f}")
            print(f"Market Impact       : ₹{d.market_impact:,.2f}")
            print(f"Estimated Slippage  : ₹{d.estimated_slippage:,.2f}")
            print(f"Execution Status    : {d.execution_status}")
        print("-" * 52)

        print("\n==================================================")
        print(" 🎉 VSC 4.5 Execution Intelligence Verified!")
        print("==================================================")

        # Assertions
        self.assertEqual(len(decisions), 2)
        for d in decisions:
            self.assertEqual(d.execution_status, "OPTIMIZED")
            self.assertGreater(d.estimated_slippage, 0.0)
            self.assertIn(d.selected_strategy, ["LIMIT_ORDER", "TWAP", "VWAP_POV"])
            self.assertEqual(d.parent_risk_id, risk_contract.immutable_id)

if __name__ == "__main__":
    unittest.main()
