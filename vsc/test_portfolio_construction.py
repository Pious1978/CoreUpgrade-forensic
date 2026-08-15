import unittest
from research.scanner.momentum_scanner import MomentumScanner
from governance.promotion.policy import ResearchPromotionPolicyEngine
from portfolio.engine import PortfolioConstructionEngine
from research.factory import ResearchSignalFactory
from .pipeline import (
    VSCPipeline,
    PipelineContext,
    GovernanceComponent,
    PortfolioIntentComponent,
    PortfolioRiskComponent,
    ExecutionPlanningComponent,
    BrokerExecutionComponent,
    FeedbackComponent,
)
from .invariants import STRUCTURAL_INVARIANTS

class MultiSignalPortfolioComponent:
    """VSC Stage component integrating multi-signal governance and portfolio construction."""
    def __init__(self, policy=None, portfolio_engine=None, factory=None):
        self.scanner = MomentumScanner()
        self.policy = policy or ResearchPromotionPolicyEngine()
        self.portfolio_engine = portfolio_engine or PortfolioConstructionEngine()
        self.factory = factory or ResearchSignalFactory()

    def transform(self, context: PipelineContext):
        candidates = self.scanner.scan()
        
        # 1. Review all candidates through governance
        results = self.policy.review_candidates(candidates)
        print("\n--- VSC 3.0 Multi-Signal Governance Audit ---")
        for res in results:
            status = "APPROVED ✅" if res.approved else "REJECTED ❌"
            print(f"[{status}] Symbol: {res.symbol}")
        print("-" * 45)

        approved_candidates = [c for c in candidates if any(r.symbol == c.symbol and r.approved for r in results)]
        
        if not approved_candidates:
            raise ValueError("No candidates approved by governance.")

        # 2. Run Portfolio Construction Engine across approved basket
        allocations = self.portfolio_engine.construct(approved_candidates)

        # For pipeline continuity, return contract for top allocated symbol (or primary intent)
        top_symbol = max(allocations, key=allocations.get)
        top_candidate = next(c for c in approved_candidates if c.symbol == top_symbol)
        
        return self.factory.create(top_candidate, context.root_contract_id, context.correlation_id)

class TestVSC3_0PortfolioConstruction(unittest.TestCase):

    def test_portfolio_construction_flow(self):
        print("\n==================================================")
        print(" Starting VSC 3.0 Portfolio Construction Test")
        print("==================================================")

        pipeline = VSCPipeline(
            research_gen=MultiSignalPortfolioComponent(),
            governance=GovernanceComponent(),
            intent_stage=PortfolioIntentComponent(),
            risk_stage=PortfolioRiskComponent(),
            planning_stage=ExecutionPlanningComponent(),
            broker_stage=BrokerExecutionComponent(),
            feedback_stage=FeedbackComponent()
        )

        pipeline_result = pipeline.run()
        contracts = pipeline_result.contracts
        signal, approved, intent, decision, plan, result, feedback = contracts

        # 1. Verify primary allocated signal is NVDA (highest conviction among approved NVDA & MSFT)
        self.assertEqual(signal.symbol, "NVDA")

        # 2. Verify structural invariants
        self.assertEqual(len(contracts), STRUCTURAL_INVARIANTS["chain_length"])

        print("\n==================================================")
        print(" 🎉 VSC 3.0 Portfolio Construction Verified!")
        print("==================================================")

if __name__ == "__main__":
    unittest.main()
