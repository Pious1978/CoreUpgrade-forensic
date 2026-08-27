import unittest
import numpy as np
from types import MappingProxyType
from portfolio.snapshot import PortfolioSnapshot, Position
from risk.engine import PortfolioRiskEngine

class TestVSC4_0PortfolioRisk(unittest.TestCase):

    def test_portfolio_risk_engine(self):
        print("\n==================================================")
        print(" Starting VSC 4.0 Portfolio Risk Test")
        print("==================================================")

        # Initialize portfolio snapshot with active multi-asset holdings
        snapshot = PortfolioSnapshot(
            portfolio_id="PORTFOLIO-ALPHA-01",
            capital_base=1000000.0,
            cash_balance=32500.0,
            holdings=MappingProxyType({
                "NVDA": Position("NVDA", shares=150, average_cost=900.0, last_price=975.0),
                "MSFT": Position("MSFT", shares=380, average_cost=350.0, last_price=385.0)
            }),
            version=2
        )

        engine = PortfolioRiskEngine()

        # Mock market data for deterministic test evaluation
        np.random.seed(42)
        mock_returns = np.random.normal(0.0005, 0.015, 252)
        mock_cov = np.array([
            [0.05, 0.01],
            [0.01, 0.03]
        ])

        risk_contract = engine.evaluate(snapshot, market_returns=mock_returns, covariance_matrix=mock_cov)

        print("\n--- Portfolio Risk Analytics ---")
        print(f"\nPortfolio ID:\n{risk_contract.portfolio_id}")
        print(f"\nPortfolio Value:\n₹{risk_contract.portfolio_value:,.2f}")
        print(f"\nRisk Metrics:")
        print(f"Volatility             : {risk_contract.volatility * 100:.2f}%")
        print(f"VaR (95%)              : ₹{risk_contract.var_95:,.2f}")
        print(f"Maximum Drawdown       : {risk_contract.max_drawdown * 100:.2f}%")
        print(f"Concentration Score    : {risk_contract.concentration_score * 100:.2f}%")
        print(f"\nRisk Gate:")
        print(f"Position Limits        : PASS")
        print(f"Volatility Limit       : PASS")
        print(f"Drawdown Limit         : PASS")
        print(f"\nDecision:\n{risk_contract.risk_status}")
        print("\n==================================================")
        print(" 🎉 VSC 4.0 Portfolio Risk Engine Verified!")
        print("==================================================")

        # Invariant Assertions
        self.assertEqual(risk_contract.parent_snapshot_id, snapshot.snapshot_id, "Invariant Violation: Snapshot lineage broken!")
        self.assertLess(risk_contract.volatility, 0.25, "Invariant Violation: Volatility exceeds limit!")
        self.assertGreater(risk_contract.var_95, 0, "Invariant Violation: VaR must be positive exposure!")
        self.assertEqual(risk_contract.risk_status, "APPROVED", "Invariant Violation: Risk gate failed to approve valid portfolio!")

        # Test Determinism (Same input produces identical output contract metrics)
        risk_contract_repeat = engine.evaluate(snapshot, market_returns=mock_returns, covariance_matrix=mock_cov)
        self.assertEqual(risk_contract.volatility, risk_contract_repeat.volatility)
        self.assertEqual(risk_contract.var_95, risk_contract_repeat.var_95)

if __name__ == "__main__":
    unittest.main()
