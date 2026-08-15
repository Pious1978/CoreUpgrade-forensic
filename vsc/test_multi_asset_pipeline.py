import unittest
from research.scanner.momentum_scanner import MomentumScanner
from governance.promotion.policy import ResearchPromotionPolicyEngine
from portfolio.snapshot import PortfolioSnapshot, Position
from portfolio.construction.allocator import RiskAwareAllocator
from types import MappingProxyType

class TestVSC3_5MultiAssetPipeline(unittest.TestCase):

    def test_multi_asset_pipeline_end_to_end(self):
        print("\n==================================================")
        print(" Starting VSC 3.5 Multi-Asset Pipeline Test")
        print("==================================================")

        scanner = MomentumScanner()
        policy = ResearchPromotionPolicyEngine()
        allocator = RiskAwareAllocator()

        candidates = scanner.scan()
        approved_candidates = [c for c in candidates if policy.evaluator.evaluate_candidate(c).approved]

        snapshot = PortfolioSnapshot(
            portfolio_id="PORTFOLIO-ALPHA-01",
            capital_base=1000000.0,
            cash_balance=250000.0,
            holdings=MappingProxyType({
                "MSFT": Position("MSFT", shares=200, average_cost=350.0, last_price=375.0)
            }),
            version=2
        )

        allocations = allocator.allocate(approved_candidates, snapshot)

        # 1. Verify multi-asset basket contains both NVDA and MSFT with correct state-aware weights (45% each, 10% cash)
        self.assertIn("NVDA", allocations)
        self.assertIn("MSFT", allocations)
        self.assertEqual(allocations["NVDA"], 0.45)
        self.assertEqual(allocations["MSFT"], 0.45)

        print("\n==================================================")
        print(" 🎉 VSC 3.5 Multi-Asset Pipeline Verified!")
        print("==================================================")

if __name__ == "__main__":
    unittest.main()
