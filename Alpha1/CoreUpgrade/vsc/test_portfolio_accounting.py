import unittest
from types import MappingProxyType
from portfolio.snapshot import PortfolioSnapshot, Position
from contracts.accounting import TradeFillContract
from portfolio.accounting import PortfolioAccountingEngine

class TestVSC3_6PortfolioAccounting(unittest.TestCase):

    def test_accounting_ledger_and_snapshot_evolution(self):
        print("\n==================================================")
        print(" Starting VSC 3.6 Portfolio Accounting Test")
        print("==================================================")

        engine = PortfolioAccountingEngine()

        # 1. Initialize Snapshot v1
        snapshot_v1 = PortfolioSnapshot(
            portfolio_id="PORTFOLIO-ALPHA-01",
            capital_base=1000000.0,
            cash_balance=500000.0,
            holdings=MappingProxyType({}),
            version=1
        )

        # 2. Simulate incoming trade fill (Buy 100 shares of NVDA at ₹900 with ₹50 fees)
        fill = TradeFillContract(
            symbol="NVDA",
            side="BUY",
            quantity=100.0,
            fill_price=900.0,
            fees=50.0
        )

        # 3. Apply accounting fill
        snapshot_v2, ledger_entries = engine.apply_fill(snapshot_v1, fill)

        # 4. Assertions
        self.assertEqual(snapshot_v2.version, 2)
        self.assertEqual(snapshot_v2.previous_snapshot_id, snapshot_v1.snapshot_id)
        self.assertIn("NVDA", snapshot_v2.holdings)
        self.assertEqual(snapshot_v2.holdings["NVDA"].shares, 100.0)
        self.assertEqual(snapshot_v2.holdings["NVDA"].average_cost, 900.5)  # (90000 + 50) / 100
        self.assertEqual(len(ledger_entries), 1)
        self.assertEqual(ledger_entries[0].transaction_type, "BUY")

        print("\n==================================================")
        print(" 🎉 VSC 3.6 Portfolio Accounting Engine Verified!")
        print("==================================================")

if __name__ == "__main__":
    unittest.main()
